#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TMDB_URL="${TMDB_URL:-https://api.themoviedb.org/3}"
TMDB_LANG="${TMDB_LANG:-ru-RU}"

if [[ -z "${TMDB_API:-}" && -f "$DIR/config/.env" ]]; then
    TMDB_API="$(
        python3 - "$DIR/config/.env" <<'PY'
import sys

env_path = sys.argv[1]

with open(env_path, encoding="utf-8") as file:
    for line in file:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        if key.strip() == "TMDB_API":
            print(value.strip().strip("'\""))
            break
PY
    )"
fi

if [[ -z "${TMDB_API:-}" ]]; then
    echo "Не найден TMDB_API. Укажи его в окружении или в config/.env." >&2
    exit 1
fi

auth_args=()
api_key_args=()

if [[ "$TMDB_API" == *.* || "$TMDB_API" == eyJ* ]]; then
    auth_args=(-H "Authorization: Bearer $TMDB_API")
else
    api_key_args=(--data-urlencode "api_key=$TMDB_API")
fi

tmp_response="$(mktemp)"
trap 'rm -f "$tmp_response"' EXIT

while true; do
    read -r -p "Введите название фильма: " movie_title

    if [[ -z "${movie_title//[[:space:]]/}" ]]; then
        echo "Название не может быть пустым."
        continue
    fi

    curl -fsS --get "$TMDB_URL/search/movie" \
        "${auth_args[@]}" \
        --data-urlencode "query=$movie_title" \
        --data-urlencode "language=$TMDB_LANG" \
        --data "include_adult=false" \
        --data "page=1" \
        "${api_key_args[@]}" \
        > "$tmp_response"

    match="$(
        python3 - "$tmp_response" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as file:
    data = json.load(file)

results = data.get("results") or []
if not results:
    sys.exit(1)

movie = results[0]
title = movie.get("title") or movie.get("original_title") or "Без названия"
original_title = movie.get("original_title")
release_date = movie.get("release_date") or ""
year = release_date[:4] if release_date else "год неизвестен"
movie_id = movie.get("id", "id неизвестен")

if original_title and original_title != title:
    print(f"{title} / {original_title} ({year}), TMDB id: {movie_id}")
else:
    print(f"{title} ({year}), TMDB id: {movie_id}")
PY
    )" || {
        echo "TMDB ничего не нашёл. Попробуйте ввести название иначе."
        continue
    }

    echo "Нашёл: $match"
    read -r -p "Это нужный фильм? [да/нет]: " answer

    case "${answer,,}" in
        да|д|yes|y)
            cat "$tmp_response"
            printf '\n'
            exit 0
            ;;
        *)
            echo "Ок, введите название ещё раз."
            ;;
    esac
done

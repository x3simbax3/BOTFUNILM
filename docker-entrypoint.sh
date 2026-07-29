#!/bin/sh
set -eu
umask 077

: "${ATLAS_DATABASE_URL:?ATLAS_DATABASE_URL is required}"

atlas migrate apply \
    --dir "file:///app/migrations" \
    --url "$ATLAS_DATABASE_URL"

exec python -m src.bot

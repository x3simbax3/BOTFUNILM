#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
make -C "$DIR" migrate
"$DIR/venv/bin/python" -m src.bot

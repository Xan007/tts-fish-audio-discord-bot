#!/usr/bin/env bash
set -euo pipefail

if ! command -v ffmpeg >/dev/null 2>&1; then
  sudo apt-get update
  sudo apt-get install -y --no-install-recommends ffmpeg libopus0
fi

if [ ! -x .venv/bin/python ]; then
  python -m venv .venv
fi

if ! .venv/bin/python -c "import discord, fishaudio, httpx, sqlalchemy" >/dev/null 2>&1; then
  .venv/bin/python -m pip install --disable-pip-version-check -r requirements.txt
fi

#!/usr/bin/env bash
set -euo pipefail

if ! command -v ffmpeg >/dev/null 2>&1; then
  if [ -f /etc/apt/sources.list.d/debian.sources ]; then
    sudo apt-get \
      -o Dir::Etc::sourcelist="sources.list.d/debian.sources" \
      -o Dir::Etc::sourceparts="-" \
      -o APT::Get::List-Cleanup="0" \
      update
  else
    sudo apt-get update
  fi
  sudo apt-get install -y --no-install-recommends ffmpeg libopus0
fi

if [ ! -x .venv/bin/python ]; then
  python -m venv .venv
fi

if ! .venv/bin/python -c "import discord, fishaudio, httpx, sqlalchemy" >/dev/null 2>&1; then
  .venv/bin/python -m pip install --disable-pip-version-check -r requirements.txt
fi

#!/usr/bin/env bash
set -euo pipefail

sudo apt-get update
sudo apt-get install -y --no-install-recommends ffmpeg libopus0
python -m pip install --user --disable-pip-version-check -r requirements.txt

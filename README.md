# TTS Discord Bot

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python Version" />
  <img src="https://img.shields.io/badge/discord.py-2.7+-5865F2?style=for-the-badge&logo=discord&logoColor=white" alt="Discord.py" />
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License MIT" />
</p>

Discord TTS bot powered by **Fish Audio**. Each user selects their own voice from the Fish Audio Voice Library; synthesis plays back in the user's voice channel in real time.

## Features

- Per-user voice selection (not a single global voice)
- Slash commands only (latest Discord API)
- Fish Audio `s2.1-pro-free` model by default (configurable)
- Speech pipeline: FIFO queue per server, one synthesis request at a time by default, playback strictly in order
- Bounded queue of 20 pending messages per server to keep memory use predictable under bursts
- Streaming playback: audio starts as soon as Fish Audio generates the first chunk (`tts.stream()`), no full-download wait
- Long text is split into short segments (max 150 chars) so long messages start in a few seconds and a failed segment is skipped instead of truncating the message
- Two modes: explicit `/tts <text>` and `/autojoin enable` for channel-wide auto-read
- Accepts voice IDs as raw UUID or `fish.audio` URLs

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) installed
- [FFmpeg](https://www.gyan.dev/ffmpeg/builds/) installed and on PATH (needed for voice playback)

## Setup

1. Copy `.env.example` to `.env` and fill in values:
   - `DISCORD_TOKEN` from https://discord.com/developers/applications
   - `FISH_API_KEY` from https://fish.audio/app/api-keys
   - `DEFAULT_VOICE_ID` from a fish.audio voice URL (e.g. https://fish.audio/voice-library/...)
   - `TTS_MODEL` defaults to `s2.1-pro-free`; use `s2.1-pro` for paid tier
   - `SPEECH_CONCURRENCY` defaults to `1`; raise it only if the host has spare CPU and memory

2. Install Discord bot intents:
   - In the Discord Developer Portal open your application -> Bot
   - Under Privileged Gateway Intents enable **MESSAGE CONTENT INTENT** (for autojoin to read messages)

3. For each server where the bot will live, invite it with scopes `bot` and `applications.commands` and permissions: `Connect`, `Speak`, `Send Messages`, `Read Message History`, `View Channels`.

4. Install dependencies and run:

```bash
uv sync
uv run python -m src.main
```

Slash commands sync to every guild the bot is in on startup (appear instantly). Global commands are cleared so they never duplicate the guild copies.

## GitHub Codespaces

This repository includes a Codespaces development container. It prepares Python 3.11, a project-local virtual environment, the locked Python dependencies, FFmpeg, and Opus support. The bot task checks and repairs missing dependencies before launch. Docker Compose is not needed for Codespaces, and the bot does not start automatically when a Codespace opens.

1. Add `DISCORD_TOKEN` and `FISH_API_KEY` as Codespaces secrets in your GitHub account settings and grant them access to this repository. `DEFAULT_VOICE_ID` is optional; the bot has a built-in default.
2. Create a Codespace from this repository. The first build installs the system audio tools and dependencies from `requirements.txt`.
3. In the Codespace, choose **Terminal → Run Task → Start Discord TTS bot**. Stop it with `Ctrl+C` in its terminal when finished.

You can instead create a `.env` file in the Codespace from `.env.example`; `.env` is ignored by Git. Do not commit bot or Fish Audio keys. No inbound port forwarding is needed because the bot connects out to Discord and Fish Audio.

Codespaces is suitable for occasional sessions, not continuous hosting: it stops after inactivity (30 minutes by default, configurable up to 4 hours) and each Codespace has a 12-hour maximum lifetime. The personal GitHub Free allowance is 120 compute core-hours and 15 GB-month of storage; a 2-core machine uses two core-hours per running hour. Set a billing budget that stops usage at the free limit if you want to avoid charges.

## Waifly deployment

Waifly manages persistent servers through its Pterodactyl panel. Its documented flow is to upload files through the panel or SFTP; it does not describe connecting a Git repository for automatic deploys. Use the Python server Egg and upload the contents of this repository so `src/` and `requirements.txt` are at the server root.

1. Create a Python server in Waifly. Python 3.11 or newer is required. The free plan is limited to 300 MiB RAM, 1 GiB disk, and 30% CPU.
2. Upload the project files, including `src/`, `requirements.txt`, and `.env.example`. Do not upload your local `.env`.
3. Install dependencies using the Python Egg's requirements installation, or run `python -m pip install -r requirements.txt` once in its console.
4. Create `.env` in the server root with `DISCORD_TOKEN`, `FISH_API_KEY`, and `DEFAULT_VOICE_ID`. Set `DB_PATH=data/bot.db` so the SQLite database stays in the server files.
5. Set the Startup command to `python -m src.main`. Enable auto-restart in the panel.
6. Confirm `ffmpeg -version` works in the server console before trying voice playback. The bot needs FFmpeg to transcode Fish Audio output for Discord. If the selected Python Egg does not include FFmpeg and does not allow installing it, ask Waifly support for a Python runtime with FFmpeg; the bot can log in without it, but voice playback will fail.
7. In the Discord Developer Portal, enable **Message Content Intent** for autojoin. The bot no longer needs the privileged Server Members Intent.

The free plan may be enough for a small test, but this bot generates and transcodes audio. Keep `SPEECH_CONCURRENCY=1` and try one voice channel first; Waifly notes that audio transcoding can exceed its free CPU allowance. Upgrade the server if playback is delayed or the process reaches its CPU or memory limit. Back up `data/bot.db` before replacing the uploaded files.

## Commands

| Command | Description |
|---|---|
| `/tts <text>` | Synthesize `text` in your configured voice. You must be in a voice channel; bot joins and plays. |
| `/voices` | Interactive voice catalog with categories (Anime, Video games, Spanish, etc.). |
| `/voice search <query>` | Search the Fish Audio public Voice Library with pagination and button selection. |
| `/voice set <ref_id_or_url>` | Save the voice for yourself. Accepts UUIDs, autocomplete, or `fish.audio` URLs. |
| `/voice set_for <user> <ref_id_or_url>` | Admin command to set another member's voice. |
| `/voice info` | Show your current voice, speed, and volume settings. |
| `/voice reset` | Reset your voice to the server default (`DEFAULT_VOICE_ID`). |
| `/voice preview [ref_id_or_url]` | Play a short sample with that voice (or your current one if omitted). |
| `/voice speed <0.5-2.0>` | Set your speech rate multiplier. |
| `/voice volume <-20 to 20>` | Set your volume adjustment in dB. |
| `/autojoin enable` | Enable auto-join on your current voice channel. Reads chat in that channel or linked text channels/threads. |
| `/autojoin disable` | Disable auto-join on your current voice channel. |
| `/stop` | Immediately stops audio playback and clears the queued messages in the server. |
| `/skip` | Skips the current audio playing in the server. |
| `/language` | Set your UI and response language preference (`auto`, `en`, `es`). |
| `/help` | Interactive quick start guide. |

## 🐳 Docker Deployment

You can run the bot in Docker with zero setup for Python or FFmpeg:

```bash
docker compose up -d --build
```

Logs can be viewed anytime via:
```bash
docker compose logs -f
```

## Architecture

```
src/
  main.py            # Entry point, extensions loader, intent handlers, slash sync
  config.py          # Environment configuration (dataclass)
  db.py              # SQLAlchemy 2.0 async engine & declarative models
  i18n.py            # Localization engine (EN/ES)
  store/             # Persistence repositories (UserVoice, Autojoin)
  fish/              # Fish Audio client, voice search, TTS streaming & synthesis
  speech/            # FIFO speech pipeline & message text sanitizers/cleaners
  audio/             # FFmpeg audio pipeline (streaming & buffer playback)
  ui/                # Interactive Discord Views (catalog, voice picker, modal, help)
  cogs/              # Discord command groups (tts, voice, autojoin, language, help)
```

Voice configurations and channel settings are persisted with **SQLAlchemy 2.0** in SQLite asynchronously. Each user's settings travel with them across servers.

## License

MIT

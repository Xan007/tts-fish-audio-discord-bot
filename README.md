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
- Speech pipeline: FIFO queue per server, up to `SPEECH_CONCURRENCY` (default 3) messages synthesized in parallel, playback strictly in order
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
   - `SPEECH_CONCURRENCY` defaults to `3`; max simultaneous Fish Audio synthesis requests

2. Install Discord bot intents:
   - In the Discord Developer Portal open your application -> Bot
   - Under Privileged Gateway Intents enable **SERVER MEMBERS INTENT** (for knowing who is in a voice channel) and **MESSAGE CONTENT INTENT** (for autojoin to read messages)

3. For each server where the bot will live, invite it with scopes `bot` and `applications.commands` and permissions: `Connect`, `Speak`, `Send Messages`, `Read Message History`, `View Channels`.

4. Install dependencies and run:

```bash
uv sync
uv run python -m src.main
```

Slash commands sync to every guild the bot is in on startup (appear instantly). Global commands are cleared so they never duplicate the guild copies.

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

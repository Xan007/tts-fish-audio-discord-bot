from __future__ import annotations

import asyncio
import logging

import discord
from discord.ext import commands

from src.config import get_config
from src.db import close_db, init_db

logger = logging.getLogger(__name__)

INTENT_WARNING = (
    "Privileged intents are not enabled. Open https://discord.com/developers/applications, "
    "select your application, go to Bot -> Privileged Gateway Intents and enable "
    "MESSAGE CONTENT INTENT. Then restart the bot."
)

COGS = ("tts", "voice", "autojoin", "help", "language")


async def _run() -> None:
    config = get_config()
    await init_db()

    intents = discord.Intents.default()
    intents.message_content = True

    bot = commands.Bot(command_prefix="!", intents=intents)

    for cog in COGS:
        await bot.load_extension(f"src.cogs.{cog}")

    commands_synced = False

    @bot.event
    async def on_ready() -> None:
        nonlocal commands_synced
        if commands_synced:
            return
        commands_synced = True
        logger.info("Logged in as %s (id %s)", bot.user, bot.user.id)
        if config.bot_description:
            await _set_bot_description(bot, config.bot_description)
        try:
            synced = await bot.tree.sync()
            logger.info("Synced %d global commands", len(synced))
        except discord.HTTPException as e:
            logger.warning("Failed to sync global commands: %s", e)
        if config.guild_id:
            guild = bot.get_guild(config.guild_id)
            if guild is not None:
                bot.tree.copy_global_to(guild=guild)
                try:
                    await bot.tree.sync(guild=guild)
                    logger.info("Synced commands to dev guild %s", guild.id)
                except discord.HTTPException as e:
                    logger.warning("Failed to sync commands to guild %s: %s", guild.id, e)

    try:
        await bot.start(config.discord_token)
    except discord.errors.PrivilegedIntentsRequired:
        logger.error(INTENT_WARNING)
    finally:
        await close_db()
        await bot.close()


async def _set_bot_description(bot: commands.Bot, description: str) -> None:
    from discord.http import Route

    try:
        await bot.http.request(
            Route("PATCH", "/applications/@me"), json={"description": description}
        )
        logger.info("Updated bot profile description.")
    except discord.HTTPException as e:
        logger.warning("Could not update bot profile description: %s", e)


def _install_intent_watcher() -> None:
    gateway = logging.getLogger("discord.gateway")
    state = {"warned": False}

    def watcher(record: logging.LogRecord) -> bool:
        if not state["warned"] and "data=4014" in record.getMessage():
            state["warned"] = True
            logger.error(INTENT_WARNING)
        return True

    gateway.addFilter(watcher)


def main() -> None:
    logging.basicConfig(level=get_config().log_level.upper())
    _install_intent_watcher()
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")


if __name__ == "__main__":
    main()

import asyncio
import logging

from pyrogram import Client, filters
from pyrogram.handlers import (
    CallbackQueryHandler,
    EditedMessageHandler,
    MessageHandler,
    RawUpdateHandler,
)

import config
import runtime
from handlers.delete import poll_deleted, sync_delete_raw
from handlers.mirror import mirror, mirror_edit
from handlers.ping import ping
from handlers.vc import vc_button, welcome

logging.basicConfig(level=logging.INFO)


async def main():
    # ------------------- BOT (mirror, buttons, ping) -------------------
    bot = Client(
        "mirror_bot",
        api_id=config.API_ID,
        api_hash=config.API_HASH,
        bot_token=config.BOT_TOKEN,
    )
    runtime.bot = bot

    bot.add_handler(
        MessageHandler(mirror, filters.chat(config.CHANNEL_A) & ~filters.service)
    )
    bot.add_handler(
        EditedMessageHandler(mirror_edit, filters.chat(config.CHANNEL_A))
    )
    bot.add_handler(MessageHandler(ping, filters.command("ping")))
    bot.add_handler(MessageHandler(welcome, filters.command("start")))
    bot.add_handler(CallbackQueryHandler(vc_button, filters.regex("^vc:")))

    await bot.start()
    print(f"Bot @{bot.me.username} is running (mirror + VC buttons)")

    # ------------------- USER (VC buttons + delete) -------------------
    session = (config.USER_SESSION or "").strip()
    if session and len(session) < 300:
        print("[USER] USER_SESSION truncated - run: python login.py")
        session = ""

    if session:
        try:
            user = Client(
                "user_session",
                api_id=config.API_ID,
                api_hash=config.API_HASH,
                session_string=session,
            )
            runtime.user = user

            user.add_handler(RawUpdateHandler(sync_delete_raw))  # instant delete
            await user.start()
            print(f"User client @{user.me.username} started (VC buttons + delete)")

            # Delete safety net - now on the USER client,
            # because bots cannot read channel history (BOT_METHOD_INVALID)
            asyncio.create_task(poll_deleted(user))
        except Exception as e:
            print(f"[USER] User client failed: {type(e).__name__}: {e}")
    else:
        print("[USER] USER_SESSION not set - VC buttons and delete are OFF")

    await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped")

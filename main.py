import asyncio
import logging

from pyrogram import Client, filters
from pyrogram.handlers import (
    EditedMessageHandler,
    MessageHandler,
    RawUpdateHandler,
)

import config
from handlers.delete import sync_delete_raw
from handlers.mirror import mirror, mirror_edit
from handlers.ping import ping
from handlers.vc import vc_raw_update, check_access

logging.basicConfig(level=logging.INFO)


async def main():
    # ------------------- BOT (mirror, edit sync, ping) -------------------
    # NOTE: no DeletedMessagesHandler here - Telegram sends no deletion
    # events to bot accounts. Delete sync lives on the user client below.
    bot = Client(
        "mirror_bot",
        api_id=config.API_ID,
        api_hash=config.API_HASH,
        bot_token=config.BOT_TOKEN,
    )

    bot.add_handler(
        MessageHandler(mirror, filters.chat(config.CHANNEL_A) & ~filters.service)
    )
    bot.add_handler(
        EditedMessageHandler(mirror_edit, filters.chat(config.CHANNEL_A))
    )
    bot.add_handler(MessageHandler(ping, filters.command("ping")))

    await bot.start()
    print(f"Bot @{bot.me.username} is running (A -> B mirror active)")

    # --------------- USER CLIENT (VC sync + delete sync) -----------------
    session = (config.USER_SESSION or "").strip()

    if session and len(session) < 300:
        print("[VC] USER_SESSION looks too short/truncated - user features disabled")
        session = ""

    if session:
        try:
            user = Client(
                "user_session",
                api_id=config.API_ID,
                api_hash=config.API_HASH,
                session_string=session,
            )
            user.add_handler(RawUpdateHandler(vc_raw_update))      # VC mirror
            user.add_handler(RawUpdateHandler(sync_delete_raw))    # delete mirror
            await user.start()
            print(f"User client @{user.me.username} started (VC sync + delete sync enabled)")

            await check_access(user)
        except Exception as e:
            print(f"[USER] User client failed to start, VC/delete sync disabled: {e}")
    else:
        print(
            "[USER] USER_SESSION not set - VC sync AND delete sync disabled "
            "(mirror/ping still work)"
        )

    await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped")

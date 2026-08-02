import asyncio
import logging

from pyrogram import Client, filters
from pyrogram.handlers import (
    EditedMessageHandler,
    MessageHandler,
    RawUpdateHandler,
)

import config
from handlers.delete import sync_delete_raw, poll_deleted
from handlers.mirror import mirror, mirror_edit
from handlers.ping import ping
from handlers.vc import vc_raw_update, check_access

logging.basicConfig(level=logging.INFO)


async def main():
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

    # Delete sync - works with bot rights alone
    asyncio.create_task(poll_deleted(bot))

    # Optional user client: adds instant delete events + VC sync
    session = (config.USER_SESSION or "").strip()
    if session and len(session) < 300:
        print("[USER] USER_SESSION too short/truncated - user features disabled")
        session = ""

    if session:
        try:
            user = Client(
                "user_session",
                api_id=config.API_ID,
                api_hash=config.API_HASH,
                session_string=session,
            )
            user.add_handler(RawUpdateHandler(vc_raw_update))
            user.add_handler(RawUpdateHandler(sync_delete_raw))
            await user.start()
            print(f"User client @{user.me.username} started (VC + instant delete enabled)")
            await check_access(user)
        except Exception as e:
            print(f"[USER] User client failed to start, VC/instant-delete disabled: {e}")

    await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped")

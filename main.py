import asyncio
import logging

from pyrogram import Client, filters
from pyrogram.handlers import EditedMessageHandler, MessageHandler, RawUpdateHandler

import config
from handlers.delete import sync_delete_raw, poll_deleted
from handlers.mirror import mirror, mirror_edit
from handlers.ping import ping
from handlers.vc import check_access, vc_raw_update, vc_reconcile

logging.basicConfig(level=logging.INFO)


async def main():
    # ------------------- BOT (mirror, delete poll, ping) -------------------
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
    asyncio.create_task(poll_deleted(bot))

    # ------------------- USER (VC sync + instant delete) -------------------
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
            user.add_handler(RawUpdateHandler(vc_raw_update))     # instant VC sync
            user.add_handler(RawUpdateHandler(sync_delete_raw))   # instant delete sync
            await user.start()
            print(f"User client @{user.me.username} started (VC + instant delete)")

            await check_access(user)
            asyncio.create_task(vc_reconcile(user))  # 10s safety net
        except Exception as e:
            print(f"[USER] User client failed: {type(e).__name__}: {e}")
    else:
        print("[USER] USER_SESSION not set -> VC sync is OFF")

    await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped")

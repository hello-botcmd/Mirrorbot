import asyncio
import logging

from pyrogram import Client, filters
from pyrogram.handlers import (
    DeletedMessagesHandler,
    EditedMessageHandler,
    MessageHandler,
    RawUpdateHandler,
)

import config
from handlers.delete import sync_delete
from handlers.mirror import mirror, mirror_edit
from handlers.ping import ping
from handlers.vc import vc_raw_update, check_access

logging.basicConfig(level=logging.INFO)


async def main():
    # ------------------- BOT (mirror, delete, ping) -------------------
    bot = Client(
        "mirror_bot",
        api_id=config.API_ID,
        api_hash=config.API_HASH,
        bot_token=config.BOT_TOKEN,
    )

    # A -> B mirroring (single posts + albums, excludes service messages)
    bot.add_handler(
        MessageHandler(mirror, filters.chat(config.CHANNEL_A) & ~filters.service)
    )
    # Edit sync (text / captions)
    bot.add_handler(
        EditedMessageHandler(mirror_edit, filters.chat(config.CHANNEL_A))
    )
    # Delete sync (chat check also done inside the handler)
    bot.add_handler(DeletedMessagesHandler(sync_delete))
    # /ping
    bot.add_handler(MessageHandler(ping, filters.command("ping")))

    await bot.start()
    print(f"Bot @{bot.me.username} is running (A -> B mirror active)")

    # ------------------- USER CLIENT (VC sync, optional) -------------------
    session = (config.USER_SESSION or "").strip()

    # Sanity check: a valid pyrogram session string is ~370 chars of base64.
    # Anything far shorter means it's empty/truncated -> don't even try.
    if session and len(session) < 300:
        print("[VC] USER_SESSION looks too short/truncated - VC sync disabled")
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
            await user.start()
            print(f"User client @{user.me.username} started (VC sync enabled)")

            # Confirm the user account can see A and manage B
            await check_access(user)
        except Exception as e:
            print(f"[VC] User client failed to start, VC sync disabled: {e}")
    else:
        print(
            "[VC] USER_SESSION not set - VC sync disabled "
            "(mirror/delete/ping still work)"
        )

    # ------------------- RUN FOREVER -------------------
    await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped")

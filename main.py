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
from handlers.vc import vc_raw_update

logging.basicConfig(level=logging.INFO)


async def main():
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

    # Voice chat sync requires a user session
    if config.USER_SESSION:
        user = Client(
            "user_session",
            api_id=config.API_ID,
            api_hash=config.API_HASH,
            session_string=config.USER_SESSION,
        )
        user.add_handler(RawUpdateHandler(vc_raw_update))
        await user.start()
            from handlers.vc import check_access
            await check_access(user)
            print(f"User client @{user.me.username} started (VC sync enabled)")
        print(f"User client @{user.me.username} started (VC sync enabled)")
    else:
        print("VC sync DISABLED - set USER_SESSION in config.py")

    await asyncio.Future()  # run forever


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped")

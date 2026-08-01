import asyncio

from pyrogram import Client

from config import CHANNEL_A, CHANNEL_B
from utils.mapping import find_mapping, save_mapping

_processing_groups = set()


async def mirror(client: Client, message):
    """Copy every post from A to B, albums included."""
    try:
        if message.media_group_id:
            key = (message.chat.id, message.media_group_id)
            if key in _processing_groups:
                return  # another message of this album is already handling it
            _processing_groups.add(key)
            try:
                # Give Telegram ~1s to deliver the whole album before copying
                await asyncio.sleep(1.0)
                group = await client.get_media_group(CHANNEL_A, message.id)
                copied = await client.copy_media_group(CHANNEL_B, CHANNEL_A, message.id)
                for src, dst in zip(group, copied):
                    save_mapping(CHANNEL_A, src.id, CHANNEL_B, dst.id,
                                 str(message.media_group_id))
            finally:
                _processing_groups.discard(key)
            return

        copied = await message.copy(chat_id=CHANNEL_B)
        save_mapping(CHANNEL_A, message.id, CHANNEL_B, copied.id)
    except Exception as e:
        print(f"[MIRROR] Failed to mirror {message.id}: {e}")


async def mirror_edit(client: Client, message):
    """Sync text/caption edits of already-mirrored posts."""
    mapping = find_mapping(CHANNEL_A, message.id)
    if not mapping or message.media_group_id:
        return
    try:
        if message.text:
            await client.edit_message_text(CHANNEL_B, mapping["dst_msg_id"], message.text)
        elif message.caption:
            await client.edit_message_caption(CHANNEL_B, mapping["dst_msg_id"], message.caption)
    except Exception:
        pass

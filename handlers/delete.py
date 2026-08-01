import logging

from pyrogram import Client
from pyrogram.raw import types

from config import CHANNEL_A, CHANNEL_B
from utils.mapping import find_mapping, remove_mapping

log = logging.getLogger("delete")


def raw_peer_id(full_chat_id: int) -> int:
    """-1004428509253 -> -4428509253 (raw peer id used inside MTProto updates)."""
    s = str(full_chat_id)
    if s.startswith("-100"):
        return -int(s[4:])
    return full_chat_id


async def sync_delete_raw(client: Client, update, users, chats):
    """
    Delete sync via raw MTProto updates.

    Bots never receive deletion updates, so this MUST be attached to the
    user client. The user account needs to be at least a subscriber of A
    to receive these updates, and admin (Delete messages) in B to perform
    the deletion.
    """
    if not isinstance(update, types.UpdateDeleteChannelMessages):
        return
    if update.channel_id != raw_peer_id(CHANNEL_A):
        return

    for msg_id in update.messages:
        mapping = find_mapping(CHANNEL_A, msg_id)
        if not mapping:
            continue
        try:
            await client.delete_messages(CHANNEL_B, mapping["dst_msg_id"])
            print(
                f"[DELETE] Post {msg_id} deleted in A -> "
                f"deleted mirrored copy {mapping['dst_msg_id']} in B"
            )
        except Exception as e:
            print(f"[DELETE] Failed to delete {mapping['dst_msg_id']} in B: {e}")
            continue
        remove_mapping(CHANNEL_A, msg_id)

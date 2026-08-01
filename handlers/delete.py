from pyrogram import Client

from config import CHANNEL_A, CHANNEL_B
from utils.mapping import find_mapping, remove_mapping


async def sync_delete(client: Client, deleted_messages):
    """When a post is deleted in A, delete its mirrored copy in B."""
    for msg in deleted_messages:
        if msg.chat.id != CHANNEL_A:
            continue
        mapping = find_mapping(CHANNEL_A, msg.id)
        if not mapping:
            continue
        try:
            await client.delete_messages(CHANNEL_B, mapping["dst_msg_id"])
        except Exception as e:
            print(f"[DELETE] Failed to delete {mapping['dst_msg_id']} in B: {e}")
        remove_mapping(CHANNEL_A, msg.id)

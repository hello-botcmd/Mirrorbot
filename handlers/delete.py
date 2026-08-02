import asyncio

from pyrogram import Client
from pyrogram.raw import types

from config import CHANNEL_A, CHANNEL_B
from utils.mapping import find_mapping, remove_mapping, list_mappings


def raw_peer_id(full_chat_id: int) -> int:
    s = str(full_chat_id)
    if s.startswith("-100"):
        return -int(s[4:])  # -1004428509253 -> -4428509253
    return full_chat_id


async def _delete_mirror(client: Client, src_msg_id: int):
    mapping = find_mapping(CHANNEL_A, src_msg_id)
    if not mapping:
        return
    try:
        await client.delete_messages(CHANNEL_B, mapping["dst_msg_id"])
        print(f"[DELETE] {src_msg_id} deleted in A -> removed {mapping['dst_msg_id']} from B")
        remove_mapping(CHANNEL_A, src_msg_id)
    except Exception as e:
        if "MESSAGE_ID_INVALID" in type(e).__name__:
            remove_mapping(CHANNEL_A, src_msg_id)  # already gone from B
        else:
            print(f"[DELETE] Failed to delete {mapping['dst_msg_id']} in B: "
                  f"{type(e).__name__}: {e}")


async def sync_delete_raw(client: Client, update, users, chats):
    """Instant path - only fires if the USER client is alive."""
    if not isinstance(update, types.UpdateDeleteChannelMessages):
        return
    if update.channel_id != raw_peer_id(CHANNEL_A):
        return
    for msg_id in update.messages:
        await _delete_mirror(client, msg_id)


async def poll_deleted(client: Client, window: int = 100, interval: float = 8.0):
    """Bot-side detection: fetch A's last `window` posts, delete any
    mirrored post whose source id is no longer there. Albiter-based, so
    albums are handled automatically. NO user session needed."""
    print(f"[DEL-POLL] watching last {window} posts of A every {interval}s "
          f"(uses bot admin rights only)")
    while True:
        try:
            existing = set()
            async for msg in client.get_chat_history(CHANNEL_A, limit=window):
                existing.add(msg.id)
            if existing:
                oldest = min(existing)
                for row in list_mappings():
                    src = row["src_msg_id"]
                    if src >= oldest and src not in existing:
                        await _delete_mirror(client, src)
        except Exception as e:
            print(f"[DEL-POLL] iteration error: {e}")
        await asyncio.sleep(interval)

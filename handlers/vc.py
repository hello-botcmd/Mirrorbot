import random

from pyrogram import Client
from pyrogram.raw import functions, types
from pyrogram.utils import get_raw_peer_id

from config import CHANNEL_A, CHANNEL_B

# Bots cannot create/end voice chats — this module requires a USER session
# (config.USER_SESSION). That user account must be an admin in both channels.


async def _get_b_call(client: Client):
    """Return the InputGroupCall of B's active voice chat, or None."""
    try:
        full = await client.invoke(
            functions.channels.GetFullChannel(
                channel=await client.resolve_peer(CHANNEL_B)
            )
        )
        gid = full.full_chat.groupcall_id
        access_hash = full.full_chat.groupcall_access_hash
        if gid and access_hash:
            return types.InputGroupCall(id=gid, access_hash=access_hash)
    except Exception:
        pass
    return None


async def vc_raw_update(client: Client, update, users, chats):
    """Mirror voice chat start/end from A to B."""
    if not isinstance(update, types.UpdateGroupCall):
        return
    if update.chat_id != get_raw_peer_id(CHANNEL_A):
        return

    call = update.call
    if isinstance(call, types.GroupCallDiscarded):
        await stop_vc(client)
    elif isinstance(call, types.GroupCall) and not call.schedule_date:
        await start_vc(client, title=call.title or "")


async def start_vc(client: Client, title: str = ""):
    existing = await _get_b_call(client)
    if existing:
        try:
            await client.invoke(
                functions.phone.EditGroupCallTitle(call=existing, title=title)
            )
            print(f"[VC] Updated voice chat title in {CHANNEL_B}")
        except Exception as e:
            print(f"[VC] Could not update title in {CHANNEL_B}: {e}")
        return

    try:
        await client.invoke(
            functions.phone.CreateGroupCall(
                peer=await client.resolve_peer(CHANNEL_B),
                random_id=random.randint(-(2**63), 2**63 - 1),
                title=title,
            )
        )
        print(f"[VC] Voice chat started in {CHANNEL_B} (title: {title!r})")
    except Exception as e:
        print(f"[VC] Failed to start voice chat in {CHANNEL_B}: {e}")


async def stop_vc(client: Client):
    call = await _get_b_call(client)
    if not call:
        print("[VC] No active voice chat in B, nothing to stop")
        return
    try:
        await client.invoke(functions.phone.DiscardGroupCall(call=call))
        print(f"[VC] Voice chat ended in {CHANNEL_B}")
    except Exception as e:
        print(f"[VC] Failed to end voice chat in {CHANNEL_B}: {e}")

import random
import logging

from pyrogram import Client
from pyrogram.raw import functions, types

from config import CHANNEL_A, CHANNEL_B

log = logging.getLogger("vc")


def raw_peer_id(full_chat_id: int) -> int:
    """-1004428509253 -> -4428509253 (raw id used inside MTProto updates)."""
    s = str(full_chat_id)
    if s.startswith("-100"):
        return -int(s[4:])
    return full_chat_id


async def _get_b_call(client: Client):
    """Current active voice chat in B, or None."""
    try:
        full = await client.invoke(
            functions.channels.GetFullChannel(
                channel=await client.resolve_peer(CHANNEL_B)
            )
        )
        gid = full.full_chat.groupcall_id
        ah = full.full_chat.groupcall_access_hash
        if gid and ah:
            return types.InputGroupCall(id=gid, access_hash=ah)
    except Exception as e:
        log.warning("Could not read current VC state of B: %s", e)
    return None


async def start_vc(client: Client, title: str = ""):
    existing = await _get_b_call(client)
    if existing:
        try:
            await client.invoke(
                functions.phone.EditGroupCallTitle(call=existing, title=title)
            )
            print(f"[VC] B already has a voice chat - title synced to {title!r}")
        except Exception as e:
            print(f"[VC] Could not sync title in B: {e}")
        return

    try:
        await client.invoke(
            functions.phone.CreateGroupCall(
                peer=await client.resolve_peer(CHANNEL_B),
                random_id=random.randint(-(2**63), 2**63 - 1),
                title=title,
            )
        )
        print(f"[VC] Voice chat STARTED in B (title {title!r})")
    except Exception as e:
        print(f"[VC] FAILED to start VC in B: {e}")


async def stop_vc(client: Client):
    call = await _get_b_call(client)
    if not call:
        print("[VC] No active VC in B, nothing to end")
        return
    try:
        await client.invoke(functions.phone.DiscardGroupCall(call=call))
        print("[VC] Voice chat ENDED in B")
    except Exception as e:
        print(f"[VC] FAILED to end VC in B: {e}")


async def vc_raw_update(client: Client, update, users, chats):
    """Mirror VC start/end from A to B."""
    if not isinstance(update, types.UpdateGroupCall):
        return
    print(
        f"[VC] Update received: chat={update.chat_id} "
        f"(A raw={raw_peer_id(CHANNEL_A)}) call={type(update.call).__name__}"
    )
    if update.chat_id != raw_peer_id(CHANNEL_A):
        return
    call = update.call
    if isinstance(call, types.GroupCallDiscarded):
        await stop_vc(client)
    elif isinstance(call, types.GroupCall):
        if call.schedule_date:
            print("[VC] Scheduled call detected - ignoring")
            return
        await start_vc(client, title=call.title or "")


async def check_access(client: Client):
    """Confirm the user account can see A and manage B."""
    me = await client.get_me()
    for name, cid in (("A", CHANNEL_A), ("B", CHANNEL_B)):
        try:
            member = await client.get_chat_member(cid, me.id)
            print(f"[VC] User account in channel {name}: {member.status}")
        except Exception:
            print(
                f"[VC] WARNING: user account is NOT a member/admin of channel {name} ({cid}). "
                f"VC mirroring will not work."
            )

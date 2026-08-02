import asyncio
import random

from pyrogram import Client
from pyrogram.raw import functions, types

from config import CHANNEL_A, CHANNEL_B


def raw_peer_id(full_chat_id: int) -> int:
    """-1004428509253 -> -4428509253 (raw id used inside MTProto updates)."""
    s = str(full_chat_id)
    if s.startswith("-100"):
        return -int(s[4:])
    return full_chat_id


async def _b_call(client: Client):
    """Live (non-discarded, non-scheduled) call currently in B, or None."""
    try:
        full = await client.invoke(
            functions.channels.GetFullChannel(
                channel=await client.resolve_peer(CHANNEL_B)
            )
        )
        gid = getattr(full.full_chat, "groupcall_id", 0) or 0
        ah = getattr(full.full_chat, "groupcall_access_hash", 0) or 0
        if not gid:
            return None
        res = await client.invoke(
            functions.phone.GetGroupCall(
                call=types.InputGroupCall(id=gid, access_hash=ah)
            )
        )
        if isinstance(res.call, types.GroupCallDiscarded):
            return None
        return types.InputGroupCall(id=gid, access_hash=ah)
    except Exception:
        return None


async def start_vc(client: Client, title: str = ""):
    """Start a live VC in B, or just sync the title if one already exists."""
    existing = await _b_call(client)
    if existing:
        try:
            await client.invoke(
                functions.phone.EditGroupCallTitle(call=existing, title=title)
            )
            print(f"[VC] B already has a call - title synced to {title!r}")
        except Exception as e:
            print(f"[VC] title sync failed: {type(e).__name__}: {e}")
        return
    try:
        await client.invoke(
            functions.phone.CreateGroupCall(
                peer=await client.resolve_peer(CHANNEL_B),
                random_id=random.randint(-2**31, 2**31 - 1),  # MUST be 32-bit
                title=title or "",
            )
        )
        print(f"[VC] STARTED voice chat in B (title {title!r})")
    except Exception as e:
        print(f"[VC] FAILED to start VC in B: {type(e).__name__}: {e}")


async def stop_vc(client: Client):
    call = await _b_call(client)
    if not call:
        print("[VC] No live call in B - nothing to end")
        return
    try:
        await client.invoke(functions.phone.DiscardGroupCall(call=call))
        print("[VC] ENDED voice chat in B")
    except Exception as e:
        print(f"[VC] FAILED to end VC in B: {type(e).__name__}: {e}")


async def vc_raw_update(client: Client, update, users, chats):
    """INSTANT path: fired the moment the VC in A changes.
       VC starts in A -> starts in B.  Ends in A -> ends in B."""
    if not isinstance(update, types.UpdateGroupCall):
        return
    if update.chat_id != raw_peer_id(CHANNEL_A):
        return
    call = update.call
    if isinstance(call, types.GroupCallDiscarded):
        print("[VC] raw update: A's call ENDED")
        await stop_vc(client)
    elif isinstance(call, types.GroupCall):
        if call.schedule_date:
            print("[VC] raw update: scheduled call in A - ignoring")
            return
        print("[VC] raw update: A's call STARTED")
        await start_vc(client, getattr(call, "title", "") or "")


async def vc_reconcile(client: Client, interval: float = 10.0):
    """Slow safety net: only fixes state if a raw update was ever missed."""
    print(f"[VC] safety-net state check every {interval}s")
    last_a = None
    while True:
        try:
            full = await client.invoke(
                functions.channels.GetFullChannel(
                    channel=await client.resolve_peer(CHANNEL_A)
                )
            )
            gid = getattr(full.full_chat, "groupcall_id", 0) or 0
            ah = getattr(full.full_chat, "groupcall_access_hash", 0) or 0
            a_on = False
            a_title = ""
            if gid:
                try:
                    res = await client.invoke(
                        functions.phone.GetGroupCall(
                            call=types.InputGroupCall(id=gid, access_hash=ah)
                        )
                    )
                    a_on = not isinstance(res.call, types.GroupCallDiscarded)
                    a_title = getattr(res.call, "title", "") or ""
                except Exception:
                    a_on = False
            if a_on != last_a:
                if a_on:
                    print("[VC] recon: A has a live call")
                    await start_vc(client, title=a_title)
                else:
                    print("[VC] recon: A's call is gone")
                    await stop_vc(client)
                last_a = a_on
        except Exception as e:
            print(f"[VC] reconcile error: {type(e).__name__}: {e}")
        await asyncio.sleep(interval)


async def check_access(client: Client):
    me = await client.get_me()
    for name, cid in (("A", CHANNEL_A), ("B", CHANNEL_B)):
        try:
            member = await client.get_chat_member(cid, me.id)
            print(f"[VC] User account in channel {name}: {member.status}")
        except Exception:
            print(
                f"[VC] WARNING: user account is NOT in channel {name} ({cid})"
            )

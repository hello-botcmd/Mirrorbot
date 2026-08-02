import asyncio
import random

from pyrogram import Client
from pyrogram.raw import functions, types
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import CHANNEL_A, CHANNEL_B

VC_START = "vc:start"
VC_END = "vc:end"
VC_TITLE = "Live"   # <-- title used when starting; change it freely

# Exact calls we created this run OR observed via updates: full_cid -> InputGroupCall
_saved_calls = {}
_observed_calls = {}


def _raw(full_cid: int) -> int:
    """-1004428509253 -> -4428509253 (raw id used inside updates)"""
    s = str(full_cid)
    return -int(s[4:]) if s.startswith("-100") else full_cid


_FULL_BY_RAW = {_raw(CHANNEL_A): CHANNEL_A, _raw(CHANNEL_B): CHANNEL_B}


async def _channel_call(client: Client, cid: int):
    """Call as reported by GetFullChannel, or None if no call at all."""
    try:
        full = await client.invoke(
            functions.channels.GetFullChannel(
                channel=await client.resolve_peer(cid)
            )
        )
        gid = getattr(full.full_chat, "groupcall_id", None)
        ah = getattr(full.full_chat, "groupcall_access_hash", None)
        if not gid:
            return None
        return types.InputGroupCall(id=gid, access_hash=ah or 0)
    except Exception as e:
        print(f"[VC] GetFullChannel({cid}) failed: {type(e).__name__}: {e}")
        return None


async def _find_live_call(client: Client, cid: int):
    """Best InputGroupCall to end for cid, or None if truly nothing is live."""
    candidates = []
    if cid in _saved_calls:
        candidates.append(_saved_calls[cid])
    if cid in _observed_calls:
        candidates.append(_observed_calls[cid])
    channel_call = await _channel_call(client, cid)
    if channel_call:
        candidates.append(channel_call)

    for call in candidates:
        try:
            res = await client.invoke(functions.phone.GetGroupCall(call=call))
            if isinstance(res.call, types.GroupCallDiscarded):
                print(f"[VC] {cid}: call {call.id} is already discarded - skipping")
                continue
            print(f"[VC] {cid}: found LIVE call {call.id}")
            return call
        except Exception as e:
            # Inconclusive probe (stale hash etc.) - still try to end it.
            print(f"[VC] {cid}: probe failed ({type(e).__name__}) - will attempt end anyway")
            return call

    print(f"[VC] {cid}: no call candidates -> nothing to end")
    return None


async def _start_in(client: Client, cid: int, title: str = VC_TITLE):
    try:
        existing = await _find_live_call(client, cid)
        if existing:
            try:
                await client.invoke(
                    functions.phone.EditGroupCallTitle(call=existing, title=title)
                )
            except Exception as e:
                print(f"[VC] {cid}: title sync failed: {type(e).__name__}: {e}")
            return f"[VC] {cid}: already live, title synced to {title!r}"

        resp = await client.invoke(
            functions.phone.CreateGroupCall(
                peer=await client.resolve_peer(cid),
                random_id=random.randint(-(2**31), 2**31 - 1),
                title=title,
            )
        )
        # Save the exact call so End can find it reliably
        saved = None
        for u in resp.updates:
            if isinstance(u, types.UpdateGroupCall) and isinstance(u.call, types.GroupCall):
                saved = types.InputGroupCall(
                    id=u.call.id, access_hash=u.call.access_hash
                )
                break
        if not saved:
            await asyncio.sleep(1.0)          # let state propagate server-side
            saved = await _channel_call(client, cid)
        if saved:
            _saved_calls[cid] = saved
        return f"[VC] {cid}: STARTED with title {title!r}"
    except Exception as e:
        return f"[VC] {cid}: FAILED {type(e).__name__}: {e}"


async def _end_in(client: Client, cid: int):
    try:
        call = await _find_live_call(client, cid)
        if not call:
            return f"[VC] {cid}: no live call, nothing to end"
        try:
            await client.invoke(functions.phone.DiscardGroupCall(call=call))
            _saved_calls.pop(cid, None)
            _observed_calls.pop(cid, None)
            return f"[VC] {cid}: ENDED"
        except Exception as e:
            return f"[VC] {cid}: FAILED {type(e).__name__}: {e}"
    except Exception as e:
        return f"[VC] {cid}: FAILED {type(e).__name__}: {e}"


async def vc_raw_update(client: Client, update, users, chats):
    """Remember calls seen in raw updates (covers VCs started manually in the app)."""
    if not isinstance(update, types.UpdateGroupCall):
        return
    full_cid = _FULL_BY_RAW.get(update.chat_id)
    if not full_cid:
        return
    if isinstance(update.call, types.GroupCallDiscarded):
        _observed_calls.pop(full_cid, None)
    elif isinstance(update.call, types.GroupCall):
        _observed_calls[full_cid] = types.InputGroupCall(
            id=update.call.id, access_hash=update.call.access_hash
        )


def vc_buttons():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("VC Start", callback_data=VC_START),
                InlineKeyboardButton("VC End", callback_data=VC_END),
            ]
        ]
    )


async def welcome(client: Client, message):
    """Small welcome message + control buttons."""
    await message.reply(
        "Welcome!\n"
        "VC Start -> starts the voice chat in BOTH channels (with title).\n"
        "VC End -> ends the voice chat in any channel that has one running.",
        reply_markup=vc_buttons(),
    )


async def vc_button(client: Client, callback_query):
    """Start/end the voice chat in A and B together."""
    from runtime import user

    if not user or not user.is_connected:
        await callback_query.answer(
            "User account not connected. Run python login.py and restart.",
            show_alert=True,
        )
        return

    if callback_query.data == VC_START:
        await callback_query.answer("Starting voice chats in both channels...")
        results = await asyncio.gather(
            _start_in(user, CHANNEL_A),
            _start_in(user, CHANNEL_B),
        )
        await callback_query.message.reply("\n".join(results))
    elif callback_query.data == VC_END:
        await callback_query.answer("Ending voice chats in both channels...")
        results = await asyncio.gather(
            _end_in(user, CHANNEL_A),
            _end_in(user, CHANNEL_B),
        )
        await callback_query.message.reply("\n".join(results))

import asyncio
import random

from pyrogram import Client
from pyrogram.raw import functions, types
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import CHANNEL_A, CHANNEL_B

VC_START = "vc:start"
VC_END = "vc:end"
VC_TITLE = "Live"   # same title applied in both channels (change freely)

# Calls created by THIS run: cid -> exact InputGroupCall from CreateGroupCall
_saved_calls = {}


def _call_from_updates(updates):
    """Extract the InputGroupCall of the newly created voice chat."""
    for u in updates.updates:
        if isinstance(u, types.UpdateGroupCall) and isinstance(u.call, types.GroupCall):
            return types.InputGroupCall(id=u.call.id, access_hash=u.call.access_hash)
    return None


async def _call_from_channel(client: Client, cid: int):
    """Best-effort: live call in cid as reported by GetFullChannel."""
    try:
        full = await client.invoke(
            functions.channels.GetFullChannel(
                channel=await client.resolve_peer(cid)
            )
        )
        gid = getattr(full.full_chat, "groupcall_id", 0) or 0
        ah = getattr(full.full_chat, "groupcall_access_hash", 0) or 0
        if not gid:
            return None
        return types.InputGroupCall(id=gid, access_hash=ah)
    except Exception as e:
        print(f"[VC] GetFullChannel({cid}) failed: {type(e).__name__}: {e}")
        return None


async def _live_call(client: Client, cid: int):
    """InputGroupCall of a LIVE (non-discarded) call in cid, or None.
    Tries the exact saved call first, then GetFullChannel."""
    for call in (_saved_calls.get(cid), await _call_from_channel(client, cid)):
        if not call:
            continue
        try:
            res = await client.invoke(
                functions.phone.GetGroupCall(call=call)
            )
            if isinstance(res.call, types.GroupCallDiscarded):
                continue
            return call
        except Exception as e:
            print(f"[VC] probe failed for call {call.id}: {type(e).__name__}: {e}")
            continue
    return None


async def _start_in(client: Client, cid: int, title: str = VC_TITLE):
    try:
        existing = await _live_call(client, cid)
        if existing:
            await client.invoke(
                functions.phone.EditGroupCallTitle(call=existing, title=title)
            )
            return f"[VC] {cid}: already live, title synced"
        resp = await client.invoke(
            functions.phone.CreateGroupCall(
                peer=await client.resolve_peer(cid),
                random_id=random.randint(-(2**31), 2**31 - 1),
                title=title,
            )
        )
        call = _call_from_updates(resp)
        if call:
            _saved_calls[cid] = call   # exact id + access hash for ending
        return f"[VC] {cid}: STARTED"
    except Exception as e:
        return f"[VC] {cid}: FAILED {type(e).__name__}: {e}"


async def _end_in(client: Client, cid: int):
    try:
        existing = await _live_call(client, cid)
        if not existing:
            return f"[VC] {cid}: no live call, nothing to end"
        # Prefer the exact call we created this run
        call = _saved_calls.get(cid) or existing
        last_err = None
        for attempt in range(3):
            try:
                await client.invoke(functions.phone.DiscardGroupCall(call=call))
                _saved_calls.pop(cid, None)
                return f"[VC] {cid}: ENDED"
            except Exception as e:
                last_err = e
                print(f"[VC] {cid} discard attempt {attempt + 1} failed: "
                      f"{type(e).__name__}: {e}")
                await asyncio.sleep(1.0)
        return f"[VC] {cid}: FAILED {type(last_err).__name__}: {last_err}"
    except Exception as e:
        return f"[VC] {cid}: FAILED {type(e).__name__}: {e}"


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
        "VC Start -> starts the voice chat in BOTH channels.\n"
        "VC End -> ends the voice chat in BOTH channels.",
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

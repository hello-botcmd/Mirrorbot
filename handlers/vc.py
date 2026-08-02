import asyncio
import random

from pyrogram import Client
from pyrogram.raw import functions, types
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import CHANNEL_A, CHANNEL_B

VC_START = "vc:start"
VC_END = "vc:end"
VC_TITLE = "Live"   # same title applied in both channels (change freely)


async def _call_in(client: Client, cid: int):
    """Live (non-discarded, non-scheduled) voice chat in cid, or None."""
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


async def _start_in(client: Client, cid: int, title: str = VC_TITLE):
    try:
        existing = await _call_in(client, cid)
        if existing:
            await client.invoke(
                functions.phone.EditGroupCallTitle(call=existing, title=title)
            )
            return f"[VC] {cid}: already live, title synced"
        await client.invoke(
            functions.phone.CreateGroupCall(
                peer=await client.resolve_peer(cid),
                random_id=random.randint(-(2**31), 2**31 - 1),
                title=title,
            )
        )
        return f"[VC] {cid}: STARTED"
    except Exception as e:
        return f"[VC] {cid}: FAILED {type(e).__name__}: {e}"


async def _end_in(client: Client, cid: int):
    try:
        existing = await _call_in(client, cid)
        if not existing:
            return f"[VC] {cid}: no live call, nothing to end"
        await client.invoke(functions.phone.DiscardGroupCall(call=existing))
        return f"[VC] {cid}: ENDED"
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

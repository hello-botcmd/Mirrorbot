import asyncio
import random

from pyrogram import Client
from pyrogram.raw import functions, types

from config import CHANNEL_A, CHANNEL_B


async def _get_call(client: Client, cid: int):
    """Return (InputGroupCall, title) if cid has a LIVE voice chat, else (None, '')."""
    try:
        full = await client.invoke(
            functions.channels.GetFullChannel(
                channel=await client.resolve_peer(cid)
            )
        )
        gid = getattr(full.full_chat, "groupcall_id", None)
        ah = getattr(full.full_chat, "groupcall_access_hash", None)
        if not gid or not ah:
            return None, ""

        call_res = await client.invoke(
            functions.phone.GetGroupCall(
                call=types.InputGroupCall(id=gid, access_hash=ah)
            )
        )
        call = call_res.call
        if isinstance(call, types.GroupCallDiscarded):
            return None, ""              # call ended
        if getattr(call, "schedule_date", None):
            return None, ""              # scheduled, not started yet
        return types.InputGroupCall(id=gid, access_hash=ah), getattr(call, "title", "") or ""
    except Exception as e:
        print(f"[VC] get_call({cid}) error: {type(e).__name__}: {e}")
        return None, ""


async def vc_poll(client: Client, interval: float = 4.0):
    """THE simple flow:
       VC starts in A  -> VC starts in B
       VC ends in A    -> VC ends in B
    """
    print(f"[VC-POLL] Mirroring voice chat A -> B every {interval}s")
    while True:
        try:
            a_call, a_title = await _get_call(client, CHANNEL_A)
            b_call, b_title = await _get_call(client, CHANNEL_B)

            a_on = a_call is not None
            b_on = b_call is not None

            if a_on and not b_on:
                try:
                    await client.invoke(
                        functions.phone.CreateGroupCall(
                            peer=await client.resolve_peer(CHANNEL_B),
                            random_id=random.randint(-(2**63), 2**63 - 1),
                            title=a_title,
                        )
                    )
                    print(f"[VC] A started VC -> STARTED in B (title {a_title!r})")
                except Exception as e:
                    print(f"[VC] FAILED to start VC in B: {type(e).__name__}: {e}")

            elif not a_on and b_on:
                try:
                    await client.invoke(functions.phone.DiscardGroupCall(call=b_call))
                    print("[VC] A ended VC -> ENDED in B")
                except Exception as e:
                    print(f"[VC] FAILED to end VC in B: {type(e).__name__}: {e}")

            elif a_on and b_on and a_title != b_title:
                try:
                    await client.invoke(
                        functions.phone.EditGroupCallTitle(call=b_call, title=a_title)
                    )
                    print(f"[VC] Title synced: {a_title!r}")
                except Exception as e:
                    print(f"[VC] Failed to sync title: {type(e).__name__}: {e}")

            # Enable this line only while debugging:
            # print(f"[VC] state A={'ON' if a_on else 'off'} | B={'ON' if b_on else 'off'}")
        except Exception as e:
            print(f"[VC] poll loop error: {type(e).__name__}: {e}")
        await asyncio.sleep(interval)

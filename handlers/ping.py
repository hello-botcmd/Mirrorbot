import time

from pyrogram import Client

START_TIME = time.time()


async def ping(client: Client, message):
    t0 = time.time()
    await client.get_me()
    latency = (time.time() - t0) * 1000
    uptime = int(time.time() - START_TIME)
    h, rem = divmod(uptime, 3600)
    m, s = divmod(rem, 60)
    await message.reply(f"Pong!\nLatency: {latency:.0f} ms\nUptime: {h}h {m}m {s}s")

#!/usr/bin/env python3
"""
login.py - Interactive OTP + 2FA session generator for mirror-bot.

Generates a valid pyrogram session string for the *user account* used
by the VC mirror feature, then writes it into config.py automatically.

Run in a real terminal:  python login.py

Handles:
  - OTP code: retry on wrong code, auto-resend when expired
  - 2FA (cloud password): hidden input, retry on wrong password
  - FloodWait: waits and continues
  - in_memory: no session files left on disk
"""

import asyncio
import getpass
import re
import sys

from pyrogram import Client
from pyrogram.errors import (
    FloodWait,
    PasswordHashInvalid,
    PasswordTooFresh,
    PhoneCodeExpired,
    PhoneCodeInvalid,
    PhoneNumberInvalid,
    SessionPasswordNeeded,
    Unauthorized,
)

API_ID = 22657083
API_HASH = "d6186691704bd901bdab275ceaab88f3"
CONFIG_FILE = "config.py"


async def input_text(prompt: str) -> str:
    loop = asyncio.get_running_loop()
    return (await loop.run_in_executor(None, input, prompt)).strip()


async def input_secret(prompt: str) -> str:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, getpass.getpass, prompt)


def patch_config(session_string: str) -> None:
    """Replace USER_SESSION in config.py with the freshly generated string."""
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            src = f.read()
        new_line = f'USER_SESSION = "{session_string}"'
        patched = re.sub(
            r"^USER_SESSION\s*=.*$",
            new_line,
            src,
            count=1,
            flags=re.MULTILINE,
        )
        if patched == src:  # line not found -> append it
            patched = src.rstrip("\n") + "\n" + new_line + "\n"
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            f.write(patched)
        print(f"[OK] USER_SESSION written to {CONFIG_FILE}")
    except Exception as e:
        print(f"[!] Could not patch {CONFIG_FILE}: {e}")
        print(f'[!] Paste manually:\nUSER_SESSION = "{session_string}"')


async def main() -> int:
    client = Client(
        "login_session",
        api_id=API_ID,
        api_hash=API_HASH,
        in_memory=True,  # nothing survives on disk except the exported string
    )
    await client.connect()
    print("Connected to Telegram.\n")

    # ---------- Step 1: phone number ----------
    while True:
        phone = await input_text("Phone number (intl format, e.g. +15551234567): ")
        phone = phone.replace(" ", "").replace("-", "")
        if not phone.startswith("+"):
            print("  Must start with '+' and country code.")
            continue
        try:
            sent = await client.send_code(phone)
            print(f"  Code sent to {phone}.")
            break
        except PhoneNumberInvalid:
            print("  Phone number is not registered on Telegram.")
        except FloodWait as e:
            print(f"  Telegram rate limit: wait {e.value}s, then retry.")
            await asyncio.sleep(e.value)

    # ---------- Step 2: OTP + 2FA ----------
    attempts = 0
    while True:
        attempts += 1
        if attempts > 8:
            print("\nToo many failed attempts. Restart the script.")
            return 1

        code = await input_text("Enter the login code (OTP): ")
        try:
            await client.sign_in(phone, sent.phone_code_hash, code)
            break  # logged in, no 2FA on this account
        except PhoneCodeInvalid:
            print("  Wrong code. Try again.")
        except PhoneCodeExpired:
            print("  Code expired; requesting a new one...")
            sent = await client.send_code(phone)
        except FloodWait as e:
            print(f"  Too many attempts: wait {e.value}s.")
            await asyncio.sleep(e.value)
        except SessionPasswordNeeded:
            print("\n  This account has 2FA enabled (cloud password).")
            pw_attempts = 0
            while True:
                pw_attempts += 1
                if pw_attempts > 5:
                    print("  Too many wrong passwords. Restart the script.")
                    return 1
                password = await input_secret("  2FA password: ")
                try:
                    await client.check_password(password)
                    print("  2FA verified.")
                    break
                except PasswordHashInvalid:
                    print("  Wrong 2FA password. Try again.")
                except PasswordTooFresh:
                    print("  Password was set too recently; try again in a few minutes.")
                except FloodWait as e:
                    print(f"  Rate limit: wait {e.value}s.")
                    await asyncio.sleep(e.value)
            break

    try:
        me = await client.get_me()
    except Unauthorized:
        print("\nLogin succeeded but the session was rejected immediately.")
        print("Open Telegram > Settings > Devices, terminate extra sessions, and rerun.")
        return 1

    print(f"\nLogged in as: {me.first_name} (@{me.username or '-'}) [id {me.id}]")

    session_string = await client.export_session_string()
    print(f"Session string length: {len(session_string)} chars")
    patch_config(session_string)

    await client.disconnect()
    print("\nDone. Now start the bot:  python main.py")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(1)

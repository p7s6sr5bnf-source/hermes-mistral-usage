#!/usr/bin/env python3
"""Store a Mistral web Cookie header on this host with owner-only permissions.

Never pass credentials on the command line; it may appear in shell history or
process listings. Run locally on the machine hosting Hermes backend.
"""
import getpass
import os
import stat
from pathlib import Path

path = Path.home() / ".config" / "hermes-mistral-usage" / "session.cookie"
folder = path.parent
folder.mkdir(parents=True, exist_ok=True, mode=0o700)
if folder.is_symlink():
    raise SystemExit("Refusing symlinked credentials directory.")
os.chmod(folder, 0o700)
if path.is_symlink():
    raise SystemExit("Refusing symlinked credentials file.")
print("Paste the Cookie request header from your authenticated Mistral browser session.")
print("It is a highly sensitive session credential, not an API key.")
cookie = getpass.getpass("Cookie: ").strip()
if not cookie or any(c in cookie for c in ("\r", "\n")) or len(cookie) > 16000:
    raise SystemExit("Invalid cookie.")
tmp = folder / (".session.cookie." + str(os.getpid()))
fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
try:
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(cookie)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
finally:
    if tmp.exists():
        tmp.unlink()
print("Saved locally with mode 0600. Restart the Hermes backend if needed.")

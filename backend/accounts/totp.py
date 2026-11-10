"""Time-based one-time passwords (RFC 6238), as used by authenticator apps.

Standard library only: HMAC-SHA1, 30-second steps, 6 digits. `verify` accepts
the previous and next step for clock drift and returns the matched step so the
caller can refuse to accept the same code twice.
"""

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

STEP_SECONDS = 30
DIGITS = 6


def generate_secret():
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _code_at(secret, step):
    key = base64.b32decode(secret + "=" * (-len(secret) % 8), casefold=True)
    digest = hmac.new(key, struct.pack(">Q", step), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    number = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(number % 10**DIGITS).zfill(DIGITS)


def current_step(now=None):
    return int((now if now is not None else time.time()) // STEP_SECONDS)


def code_for(secret, now=None):
    return _code_at(secret, current_step(now))


def verify(secret, code, *, last_step=-1, now=None):
    """Return the matching time step, or None. Steps <= last_step are rejected (replay)."""

    code = "".join(ch for ch in str(code) if ch.isdigit())
    if not secret or len(code) != DIGITS:
        return None
    step = current_step(now)
    for candidate in (step - 1, step, step + 1):
        if candidate > last_step and hmac.compare_digest(_code_at(secret, candidate), code):
            return candidate
    return None


def provisioning_uri(secret, username, issuer="Infogram"):
    label = quote(f"{issuer}:{username}")
    return f"otpauth://totp/{label}?secret={secret}&issuer={quote(issuer)}&algorithm=SHA1&digits={DIGITS}&period={STEP_SECONDS}"


def new_recovery_codes(count=8):
    """Plain codes to show once, plus their hashes to store."""

    codes = [f"{secrets.token_hex(2)}-{secrets.token_hex(2)}" for _ in range(count)]
    return codes, [hash_recovery_code(code) for code in codes]


def hash_recovery_code(code):
    return hashlib.sha256(code.strip().lower().encode()).hexdigest()

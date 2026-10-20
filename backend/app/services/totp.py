import hashlib
import hmac
import secrets
from datetime import datetime, timezone
from urllib.parse import quote

BASE32_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
SECRET_BYTES = 20
STEP_SECONDS = 30
DIGITS = 6


def generate_secret() -> str:
    return base32_encode(secrets.token_bytes(SECRET_BYTES))


def build_otpauth_uri(email: str, secret: str) -> str:
    label = quote(f"SufferTracker:{email}", safe="")
    issuer = quote("SufferTracker", safe="")
    return f"otpauth://totp/{label}?secret={secret}&issuer={issuer}&digits={DIGITS}&period={STEP_SECONDS}&algorithm=SHA1"


def validate_code(secret: str, code: str | None, now: datetime | None = None) -> bool:
    if not code or not code.strip():
        return False
    cleaned = code.strip().replace(" ", "")
    if len(cleaned) != DIGITS or not cleaned.isdigit():
        return False
    try:
        key = base32_decode(secret)
    except ValueError:
        return False
    if not key:
        return False
    moment = now or datetime.now(timezone.utc)
    step = int(moment.timestamp()) // STEP_SECONDS
    return any(_hotp(key, step + offset) == cleaned for offset in (0, -1, 1))


def generate_code(secret: str, now: datetime) -> str:
    return _hotp(base32_decode(secret), int(now.timestamp()) // STEP_SECONDS)


def base32_encode(data: bytes) -> str:
    if not data:
        return ""
    chars: list[str] = []
    buffer = 0
    bits = 0
    for value in data:
        buffer = (buffer << 8) | value
        bits += 8
        while bits >= 5:
            chars.append(BASE32_ALPHABET[(buffer >> (bits - 5)) & 0x1F])
            bits -= 5
    if bits:
        chars.append(BASE32_ALPHABET[(buffer << (5 - bits)) & 0x1F])
    return "".join(chars)


def base32_decode(value: str) -> bytes:
    trimmed = "".join(char for char in value if char.isalnum()).upper()
    if not trimmed:
        return b""
    output = bytearray(len(trimmed) * 5 // 8)
    buffer = 0
    bits = 0
    position = 0
    for character in trimmed:
        index = BASE32_ALPHABET.find(character)
        if index < 0:
            raise ValueError(f"Invalid base32 character '{character}'.")
        buffer = (buffer << 5) | index
        bits += 5
        if bits >= 8:
            output[position] = (buffer >> (bits - 8)) & 0xFF
            position += 1
            bits -= 8
    return bytes(output)


def _hotp(key: bytes, counter: int) -> str:
    counter_bytes = (counter & 0xFFFFFFFFFFFFFFFF).to_bytes(8, "big")
    digest = hmac.new(key, counter_bytes, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    binary = ((digest[offset] & 0x7F) << 24) | (digest[offset + 1] << 16) | (digest[offset + 2] << 8) | digest[offset + 3]
    return f"{binary % 1_000_000:0{DIGITS}d}"

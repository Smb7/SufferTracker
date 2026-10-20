from datetime import datetime, timedelta, timezone

import pytest

from app.services.totp import base32_decode, base32_encode, build_otpauth_uri, generate_code, generate_secret, validate_code

RFC_VECTOR = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"
T0 = datetime(1970, 1, 1, tzinfo=timezone.utc)


@pytest.mark.parametrize(("unix_seconds", "expected"), [(59, "287082"), (1111111109, "081804"), (1234567890, "005924")])
def test_validate_accepts_rfc6238_sha1_vectors(unix_seconds: int, expected: str) -> None:
    moment = T0 + timedelta(seconds=unix_seconds)
    assert generate_code(RFC_VECTOR, moment) == expected
    assert validate_code(RFC_VECTOR, expected, moment)


def test_validate_accepts_adjacent_window_for_clock_skew() -> None:
    assert validate_code(RFC_VECTOR, "287082", T0 + timedelta(seconds=89))
    assert validate_code(RFC_VECTOR, "287082", T0 + timedelta(seconds=29))


@pytest.mark.parametrize(("code", "expected"), [("287082", True), (" 287082 ", True), (" 287 082 ", True), ("287083", False)])
def test_validate_normalizes_whitespace_and_rejects_wrong_digits(code: str, expected: bool) -> None:
    assert validate_code(RFC_VECTOR, code, T0 + timedelta(seconds=59)) is expected


def test_validate_rejects_code_from_distant_window() -> None:
    assert validate_code(RFC_VECTOR, "287082", T0 + timedelta(seconds=59 + 30 * 5)) is False


@pytest.mark.parametrize("code", [None, "", "28708", "2870821", "28708a", "abcdef"])
def test_validate_rejects_malformed_codes(code: str | None) -> None:
    assert validate_code(RFC_VECTOR, code, T0 + timedelta(seconds=59)) is False


def test_validate_returns_false_for_invalid_base32_secret() -> None:
    assert validate_code("not!valid@base32", "287082", T0 + timedelta(seconds=59)) is False


def test_generate_secret_produces_decodable_unique_secrets() -> None:
    first = generate_secret()
    second = generate_secret()
    assert first != second
    assert len(first) == 32
    assert first.isupper() and all(char in "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567" for char in first)
    assert len(base32_decode(first)) == 20


@pytest.mark.parametrize(
    ("encoded", "decoded"),
    [
        ("", b""),
        ("MY", bytes([0x66])),
        ("MZXQ", bytes([0x66, 0x6F])),
        ("MZXW6", bytes([0x66, 0x6F, 0x6F])),
        ("MZXW6YQ", bytes([0x66, 0x6F, 0x6F, 0x62])),
        ("MZXW6YTB", bytes([0x66, 0x6F, 0x6F, 0x62, 0x61])),
    ],
)
def test_base32_round_trips_rfc4648_vectors(encoded: str, decoded: bytes) -> None:
    assert base32_encode(decoded) == encoded
    assert base32_decode(encoded) == decoded


def test_build_otpauth_uri_escapes_account_and_issuer() -> None:
    uri = build_otpauth_uri("user+tag@example.com", RFC_VECTOR)
    assert uri.startswith("otpauth://totp/")
    assert "SufferTracker%3Auser%2Btag%40example.com" in uri
    assert f"secret={RFC_VECTOR}" in uri
    assert "digits=6" in uri
    assert "period=30" in uri

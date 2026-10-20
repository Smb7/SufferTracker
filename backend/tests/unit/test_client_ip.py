import pytest
from starlette.requests import Request

from app.services.client_ip import client_ip, is_public


@pytest.mark.parametrize(
    ("ip", "expected"),
    [
        ("8.8.8.8", True),
        ("1.1.1.1", True),
        ("127.0.0.1", False),
        ("::1", False),
        ("10.0.0.4", False),
        ("192.168.1.20", False),
        ("172.16.0.2", False),
        ("172.31.255.1", False),
        ("169.254.1.1", False),
        ("not-an-ip", False),
    ],
)
def test_is_public_classifies_addresses(ip: str, expected: bool) -> None:
    assert is_public(ip) is expected


def test_client_ip_prefers_forwarded_for() -> None:
    scope = {
        "type": "http",
        "headers": [(b"x-forwarded-for", b"203.0.113.10, 10.0.0.1")],
        "client": ("127.0.0.1", 1234),
    }
    assert client_ip(Request(scope)) == "203.0.113.10"

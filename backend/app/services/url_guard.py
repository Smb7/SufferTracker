import ipaddress
import socket
from urllib.parse import urlparse


class UrlGuardError(ValueError):
    pass


def validate_public_http_url(url: str | None) -> str:
    raw = (url or "").strip()
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise UrlGuardError("A valid HTTP or HTTPS URL is required.")
    if parsed.username or parsed.password:
        raise UrlGuardError("URLs containing embedded credentials are not allowed.")
    host = parsed.hostname
    if not host:
        raise UrlGuardError("The URL host could not be resolved to a public address.")
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None:
        _ensure_public(literal)
        return raw
    try:
        addresses = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise UrlGuardError("The URL host could not be resolved to a public address.") from exc
    if not addresses:
        raise UrlGuardError("The URL host could not be resolved to a public address.")
    for item in addresses:
        _ensure_public(ipaddress.ip_address(item[4][0]))
    return raw


def _ensure_public(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> None:
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        address = address.ipv4_mapped
    blocked = address.is_loopback or address.is_unspecified or address.is_link_local or getattr(address, "is_site_local", False)
    if isinstance(address, ipaddress.IPv4Address):
        octets = list(address.packed)
        blocked = blocked or octets[0] in (0, 10, 127) or (octets[0] == 100 and 64 <= octets[1] <= 127) or (octets[0] == 169 and octets[1] == 254) or (octets[0] == 172 and 16 <= octets[1] <= 31) or (octets[0] == 192 and octets[1] == 168)
    if blocked or str(address) in {"255.255.255.255", "::"}:
        raise UrlGuardError("Requests to private or internal network addresses are not allowed.")

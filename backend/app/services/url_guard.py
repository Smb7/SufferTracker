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
    if address.is_multicast or not address.is_global:
        raise UrlGuardError("Requests to private or internal network addresses are not allowed.")

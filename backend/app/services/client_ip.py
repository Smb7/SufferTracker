import ipaddress

from fastapi import Request


def client_ip(request: Request) -> str:
    peer = request.client.host if request.client and request.client.host else ""
    forwarded = request.headers.get("x-forwarded-for")
    # Only a trusted hop (loopback, private, or the test client) may supply the
    # header. Use the last entry, which is the address that hop appended.
    if forwarded and _trust_forwarded_header(peer):
        parts = [part.strip() for part in forwarded.split(",") if part.strip()]
        if parts:
            return parts[-1][:64]
    return peer or "unknown"


def _trust_forwarded_header(peer: str) -> bool:
    if not peer or peer == "testclient":
        return True
    try:
        ipaddress.ip_address(peer)
    except ValueError:
        return False
    return not is_public(peer)


def is_public(ip: str) -> bool:
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return False
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        address = address.ipv4_mapped
    if address.is_loopback:
        return False
    if isinstance(address, ipaddress.IPv4Address):
        octets = address.packed
        if octets[0] in (0, 10, 127):
            return False
        if octets[0] == 169 and octets[1] == 254:
            return False
        if octets[0] == 172 and 16 <= octets[1] <= 31:
            return False
        if octets[0] == 192 and octets[1] == 168:
            return False
        return True
    first = address.packed[0]
    return not address.is_link_local and first not in (0x00, 0xFC, 0xFD)

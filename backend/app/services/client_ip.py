import ipaddress

from fastapi import Request


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded and forwarded.strip():
        return forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


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

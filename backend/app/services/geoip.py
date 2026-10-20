from dataclasses import dataclass

import httpx

from app.services.client_ip import is_public


@dataclass(frozen=True)
class GeoResult:
    latitude: float
    longitude: float
    city: str | None
    country: str | None


def lookup(ip: str, client: httpx.Client | None = None) -> GeoResult | None:
    if not is_public(ip):
        return None
    owns_client = client is None
    http = client or httpx.Client(timeout=2)
    try:
        response = http.get(f"http://ip-api.com/json/{ip}", params={"fields": "status,lat,lon,city,country"})
        response.raise_for_status()
        payload = response.json()
        if str(payload.get("status", "")).lower() != "success":
            return None
        return GeoResult(float(payload["lat"]), float(payload["lon"]), payload.get("city"), payload.get("country"))
    except Exception:
        return None
    finally:
        if owns_client:
            http.close()

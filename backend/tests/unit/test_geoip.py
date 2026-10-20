import httpx

from app.services.geoip import lookup


def test_lookup_skips_private_addresses() -> None:
    assert lookup("127.0.0.1", client=httpx.Client()) is None
    assert lookup("not-an-ip") is None


def test_lookup_reads_successful_payload() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["fields"] == "status,lat,lon,city,country"
        return httpx.Response(200, json={"status": "success", "lat": 40.7, "lon": -74.0, "city": "New York", "country": "United States"})

    result = lookup("8.8.8.8", client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert result is not None
    assert result.city == "New York"
    assert result.latitude == 40.7


def test_lookup_returns_none_when_provider_fails() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    assert lookup("1.1.1.1", client=httpx.Client(transport=httpx.MockTransport(handler))) is None

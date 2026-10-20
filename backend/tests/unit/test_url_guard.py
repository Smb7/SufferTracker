import pytest

from app.services.url_guard import UrlGuardError, validate_public_http_url


@pytest.mark.parametrize(
    "url",
    [
        "not a url",
        "ftp://example.com/job",
        "/relative/path",
        "http://user:pass@example.com/job",
        "https://example@host/job",
        "http://127.0.0.1/jobs",
        "http://localhost/jobs",
        "https://[::1]/jobs",
        "http://[::ffff:10.0.0.5]/jobs",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.1.2.3/jobs",
        "http://192.168.1.10/jobs",
        "http://172.16.0.9/jobs",
        "http://172.31.255.255/jobs",
        "http://100.100.1.1/jobs",
        "http://0.0.0.0/jobs",
    ],
)
def test_validate_rejects_non_public_or_invalid_urls(url: str) -> None:
    with pytest.raises(UrlGuardError):
        validate_public_http_url(url)


def test_validate_accepts_public_ip_literals() -> None:
    assert validate_public_http_url("https://8.8.8.8/jobs/123") == "https://8.8.8.8/jobs/123"
    assert validate_public_http_url("http://172.32.0.9/jobs") == "http://172.32.0.9/jobs"
    assert validate_public_http_url("http://1.1.1.1/jobs") == "http://1.1.1.1/jobs"
    assert validate_public_http_url("http://8.7.6.5/jobs") == "http://8.7.6.5/jobs"

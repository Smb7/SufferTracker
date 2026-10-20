from datetime import datetime

import pytest

from app.services.stats import week_start


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        ("2026-08-25T15:30:00+00:00", "2026-08-24T00:00:00+00:00"),
        ("2026-08-24T00:00:01+00:00", "2026-08-24T00:00:00+00:00"),
        ("2026-08-30T23:59:59+00:00", "2026-08-24T00:00:00+00:00"),
    ],
)
def test_week_start_returns_monday(now: str, expected: str) -> None:
    assert week_start(datetime.fromisoformat(now)) == datetime.fromisoformat(expected)


def test_public_stats_counts_this_week(client) -> None:
    response = client.get("/api/stats/public")
    assert response.status_code == 200
    assert response.json() == {"applicationsThisWeek": 0}

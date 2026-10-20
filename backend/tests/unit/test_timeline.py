import pytest

from app.services.timeline import TimelineError, synthesize, validate


def test_validate_accepts_applied_only() -> None:
    events = validate(["Applied"])
    assert len(events) == 1
    assert events[0]["status"] == "Applied"


def test_validate_accepts_sequential_interview_rounds() -> None:
    events = validate(["Applied", "Interview", "Interview", "Interview"])
    assert len(events) == 4
    assert sum(item["status"] == "Interview" for item in events) == 3


def test_validate_unlocks_offer_after_interview() -> None:
    assert validate(["Applied", "Interview", "JobOffer"])[-1]["status"] == "JobOffer"


def test_validate_rejects_offer_without_interview() -> None:
    with pytest.raises(TimelineError, match="interview"):
        validate(["Applied", "JobOffer"])


def test_validate_rejects_timelines_not_starting_with_applied() -> None:
    with pytest.raises(TimelineError):
        validate(["Interview"])
    with pytest.raises(TimelineError):
        validate([])


def test_validate_rejects_applied_appearing_twice() -> None:
    with pytest.raises(TimelineError):
        validate(["Applied", "Interview", "Applied"])


def test_validate_nothing_follows_terminal_statuses() -> None:
    with pytest.raises(TimelineError):
        validate(["Applied", "Rejected", "Interview"])
    with pytest.raises(TimelineError):
        validate(["Applied", "Ghosted", "JobOffer"])
    with pytest.raises(TimelineError):
        validate(["Applied", "Interview", "JobOffer", "Interview"])


def test_terminal_statuses_are_reachable() -> None:
    assert validate(["Applied", "Rejected"])[-1]["status"] == "Rejected"
    assert validate(["Applied", "Interview", "Ghosted"])[-1]["status"] == "Ghosted"


@pytest.mark.parametrize(
    ("target", "round_count", "expected"),
    [("Waiting", None, ["Applied"]), ("Interview", 3, ["Applied", "Interview", "Interview", "Interview"])],
)
def test_synthesize_builds_valid_prefixes(target: str, round_count: int | None, expected: list[str]) -> None:
    timeline = synthesize(target, round_count)
    assert timeline == expected
    validate(timeline)

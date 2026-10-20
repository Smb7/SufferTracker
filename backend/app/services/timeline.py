from datetime import datetime, timezone

TERMINAL = {"JobOffer", "Ghosted", "Rejected"}
MAX_INTERVIEW_ROUNDS = 10


class TimelineError(ValueError):
    pass


def validate(requested: list[str]) -> list[dict]:
    if not requested:
        raise TimelineError("A status timeline is required.")
    if requested[0] != "Applied":
        raise TimelineError("Every application starts with an 'Applied' status.")

    events: list[dict] = []
    interview_round = 0
    for status in requested:
        if events and status == "Interview" and events[-1]["status"] == "Interview":
            pass
        elif events and events[-1]["status"] == status:
            continue
        if events and events[-1]["status"] in TERMINAL:
            raise TimelineError(f"'{events[-1]['status']}' is final; no further statuses can be added after it.")
        if status == "Waiting":
            continue
        if status == "Applied":
            if events:
                raise TimelineError("'Applied' can only appear once, at the start of the timeline.")
        elif status == "Interview":
            if interview_round >= MAX_INTERVIEW_ROUNDS:
                raise TimelineError("Interview rounds cannot exceed 10.")
            interview_round += 1
        elif status == "JobOffer" and interview_round == 0:
            raise TimelineError("Record at least one interview before marking a job offer.")
        events.append({"status": status, "occurredAtUtc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")})
    return events


def synthesize(target: str, interview_round: int | None) -> list[str]:
    round_count = min(10, max(1, interview_round if interview_round is not None else 1))
    timeline = ["Applied"]
    if target == "Waiting":
        return timeline
    if target == "Interview":
        timeline.extend(["Interview"] * round_count)
        return timeline
    if target == "JobOffer":
        timeline.extend(["Interview", "JobOffer"])
        return timeline
    timeline.append(target)
    return timeline

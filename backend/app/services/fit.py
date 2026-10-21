"""Server-owned fit score. A model must not pick this number.

Required coverage is 70 points, preferred coverage is 20, and title-token
overlap is 10. Preferred matches cannot hide a missing required term.
Interests and next-job goals are not read.
"""

import re

from app.services.evidence import has_scoreable_evidence, normalize_key, source_for
from app.services.requirements import extract_requirements

FINISH_ONBOARDING = "Finish onboarding."
_TITLE_SKIP = {
    "senior", "junior", "lead", "staff", "principal", "associate", "intern", "sr", "jr",
    "remote", "hybrid", "onsite", "the", "and", "for", "with",
}
_TOKEN = re.compile(r"[A-Za-z][\w#+./+-]{1,40}")


def score_fit(evidence: dict, requirements: dict) -> dict:
    if not has_scoreable_evidence(evidence):
        return _blocked(FINISH_ONBOARDING, profile_blocked=True)
    reason = requirements.get("blockedReason")
    if reason:
        return _blocked(str(reason), profile_blocked=False)

    must = _must_match(requirements)
    preferred = list(requirements.get("preferred") or [])
    matched: list[dict] = []
    missing: list[str] = []
    must_hits = _cover(evidence, must, matched, missing)
    preferred_hits = _cover(evidence, preferred, matched, missing)
    required_coverage = must_hits / len(must) if must else 0.0
    preferred_coverage = preferred_hits / len(preferred) if preferred else 0.0
    alignment = title_alignment(evidence, requirements)
    raw = required_coverage * 70 + preferred_coverage * 20 + alignment * 10
    score = max(0, min(100, int(round(raw))))
    return {
        "score": score,
        "blockedReason": None,
        "profileBlocked": False,
        "matched": matched,
        "missing": missing,
        "titleAlignment": round(alignment, 2),
    }


def score_job(evidence: dict, *, title: str, company: str = "", description: str = "", skills: str = "") -> dict:
    return score_fit(evidence, extract_requirements(title, company, description, skills))


def title_alignment(evidence: dict, requirements: dict) -> float:
    """Overlap between the job title and recorded role titles. Goals are ignored."""
    wanted = _title_tokens(str(requirements.get("title") or ""))
    if not wanted:
        return 0.0
    held: set[str] = set()
    for role in evidence.get("roles") or []:
        if isinstance(role, dict):
            held |= _title_tokens(str(role.get("title") or ""))
    if not held:
        return 0.0
    return len(wanted & held) / len(wanted)


def _must_match(requirements: dict) -> list[str]:
    required = list(requirements.get("required") or [])
    if required:
        return required
    preferred = {normalize_key(item) for item in requirements.get("preferred") or []}
    return [item for item in requirements.get("keywords") or [] if normalize_key(item) not in preferred]


def _cover(evidence: dict, terms: list[str], matched: list[dict], missing: list[str]) -> int:
    hits = 0
    seen = {normalize_key(item["term"]) for item in matched}
    for term in terms:
        key = normalize_key(term)
        if not key or key in seen:
            continue
        seen.add(key)
        source = source_for(evidence, term)
        if source:
            matched.append({"term": term, "source": source})
            hits += 1
        else:
            missing.append(term)
    return hits


def _title_tokens(text: str) -> set[str]:
    tokens: set[str] = set()
    for token in _TOKEN.findall(text):
        key = normalize_key(token)
        if len(key) < 3 or key in _TITLE_SKIP:
            continue
        tokens.add(key)
    return tokens


def _blocked(reason: str, *, profile_blocked: bool) -> dict:
    return {
        "score": None,
        "blockedReason": reason,
        "profileBlocked": profile_blocked,
        "matched": [],
        "missing": [],
        "titleAlignment": None,
    }

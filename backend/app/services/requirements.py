"""Turn a job posting into required, preferred, and other keywords.

The server extracts terms. It does not invent them. A requirements or
qualifications section is required. A preferred or nice-to-have section is
preferred. Everything else is a keyword only when it is a skill line, a known
skill, or an obvious tool or credential token.
"""

import re

from app.services.evidence import distinctive_tokens, normalize_key
from app.services.parser import KNOWN_SKILLS, parse_text

REQUIRED_CAP = 40
PREFERRED_CAP = 40
KEYWORD_CAP = 80
EMPTY_TEXT = "The posting has no usable text."
NO_TERMS = "The posting has no usable terms."

_REQUIRED_LABELS = {
    "requirements", "requirement", "qualifications", "qualification",
    "required qualifications", "required skills", "required experience",
    "minimum qualifications", "minimum requirements", "basic qualifications",
    "what youll need", "what you will need", "what youll bring", "what you will bring",
    "must have", "must haves", "must-haves", "key requirements",
}
_PREFERRED_LABELS = {
    "preferred", "preferred qualifications", "preferred skills", "preferred experience",
    "nice to have", "nice-to-have", "nice to haves", "bonus", "bonus points", "pluses", "plus",
}
_SKILL_LABELS = {"skills", "skill", "technologies", "technology", "tech stack", "tools", "our stack"}
_BREAK_LABELS = {
    "about", "about the role", "about us", "about the company", "responsibilities", "responsibility",
    "what you ll do", "what you will do", "benefits", "who we are", "the role", "job description",
    "overview", "summary", "our mission",
}
_FILLER = re.compile(
    r"^(?:at least\s+)?(?:\d+\+?\s+years?(?: of)?|experience (?:with|in|using)|proficient (?:in|with)|"
    r"knowledge of|familiarity with|familiar with|working knowledge of|hands[- ]on experience with|"
    r"strong|solid|current|ability to|must have|required)\s+",
    re.I,
)
_LIST_SEP = re.compile(r"[,;\n•|/]|\band\b", re.I)
_BULLET = re.compile(r"^(?:[-*•]+\s*|\d+[.)]\s+)")


def extract_requirements(
    title: str = "",
    company: str = "",
    description: str = "",
    skills: str = "",
) -> dict:
    """Keywords for a saved job or a pasted title plus text. Recomputes every call."""
    text = description.strip()
    skill_text = skills.strip()
    parsed_title, parsed_company, parsed_skills = _from_parser(text)
    resolved_title = title.strip() or parsed_title
    resolved_company = company.strip() or parsed_company
    if not text and not skill_text:
        return _empty(resolved_title, resolved_company, EMPTY_TEXT)

    required = _collect(text, "required", phrases=True)
    preferred = _collect(text, "preferred", phrases=True)
    claimed = {normalize_key(item) for item in required + preferred}
    other: list[str] = []
    other_seen = set(claimed)
    for term in (
        _collect(text, "skills", phrases=True)
        + _collect(text, "other", phrases=False)
        + _skill_terms(skill_text)
        + _skill_terms(parsed_skills)
        + _known_hits(text)
        + distinctive_tokens(text)
    ):
        _add(other, other_seen, term, KEYWORD_CAP)

    keywords = _merge(required, preferred, other)
    if not keywords:
        return _empty(resolved_title, resolved_company, NO_TERMS)
    return {
        "title": resolved_title,
        "company": resolved_company,
        "required": required,
        "preferred": preferred,
        "keywords": keywords,
        "blockedReason": None,
    }


def _from_parser(text: str) -> tuple[str, str, str]:
    if not text:
        return "", "", ""
    try:
        parsed = parse_text(text)
    except ValueError:
        return "", "", ""
    title = "" if parsed.title == "Untitled role" else parsed.title
    company = "" if parsed.company == "Unknown company" else parsed.company
    skills = ", ".join(skill for skill in _split_list(parsed.skills) if _known_or_short(skill, text))
    return title, company, skills


def _known_or_short(skill: str, text: str) -> bool:
    if _boundary_hit(skill, text):
        return True
    return len(skill.split()) <= 6 and len(skill) <= 80


def _sections(text: str) -> list[tuple[str, str]]:
    kind = "other"
    lines: list[tuple[str, str]] = []
    for raw in text.replace("\r", "\n").split("\n"):
        header = _header(raw)
        if header is not None:
            kind, inline = header
            if inline:
                lines.append((kind, inline))
            continue
        if not raw.strip():
            continue
        lines.append((kind, raw.strip()))
    return lines


def _header(line: str) -> tuple[str, str] | None:
    stripped = _BULLET.sub("", line).strip()
    if not stripped or len(stripped) > 80:
        return None
    label, separator, rest = stripped.partition(":")
    key = normalize_key(label)
    if separator and key in _REQUIRED_LABELS:
        return "required", rest.strip()
    if separator and key in _PREFERRED_LABELS:
        return "preferred", rest.strip()
    if separator and key in _SKILL_LABELS:
        return "skills", rest.strip()
    if separator:
        return None
    if key in _REQUIRED_LABELS:
        return "required", ""
    if key in _PREFERRED_LABELS:
        return "preferred", ""
    if key in _SKILL_LABELS:
        return "skills", ""
    if key in _BREAK_LABELS:
        return "other", ""
    return None


def _collect(text: str, kind: str, *, phrases: bool) -> list[str]:
    bucket: list[str] = []
    seen: set[str] = set()
    cap = REQUIRED_CAP if kind == "required" else PREFERRED_CAP if kind == "preferred" else KEYWORD_CAP
    for section, line in _sections(text):
        if section != kind:
            continue
        for term in _terms_from_line(line, phrases=phrases):
            _add(bucket, seen, term, cap)
    return bucket


def _terms_from_line(line: str, *, phrases: bool) -> list[str]:
    cleaned = _BULLET.sub("", line).strip()
    if len(cleaned) < 2:
        return []
    if _is_long(cleaned):
        return distinctive_tokens(cleaned) + _known_hits(cleaned)
    parts = _split_list(cleaned) or [cleaned]
    terms: list[str] = []
    for part in parts:
        phrase = _strip_filler(part)
        if not phrase:
            continue
        if not phrases or _is_long(phrase):
            terms.extend(distinctive_tokens(phrase) or _known_hits(phrase))
            continue
        terms.append(phrase)
    return terms


def _skill_terms(text: str) -> list[str]:
    parts = _split_list(text)
    if parts:
        return parts
    cleaned = " ".join(text.split()).strip(" .-")
    if 2 <= len(cleaned) <= 80 and len(cleaned.split()) <= 6 and not _is_long(cleaned):
        return [cleaned]
    return []


def _split_list(text: str) -> list[str]:
    raw = text.strip()
    if not raw or not _LIST_SEP.search(raw):
        return []
    if len(raw) > 400:
        return []
    parts: list[str] = []
    for part in _LIST_SEP.split(raw):
        cleaned = " ".join(part.strip(" .:-•*").split())
        if 2 <= len(cleaned) <= 80 and len(cleaned.split()) <= 8:
            parts.append(cleaned)
    return parts


def _strip_filler(text: str) -> str:
    cleaned = " ".join(text.strip(" .:-•*").split())
    previous = None
    while cleaned and cleaned != previous:
        previous = cleaned
        cleaned = _FILLER.sub("", cleaned).strip()
    if len(cleaned) < 2 or len(cleaned.split()) > 8:
        return ""
    return cleaned


def _known_hits(text: str) -> list[str]:
    return [skill for skill in KNOWN_SKILLS if _boundary_hit(skill, text)]


def _boundary_hit(skill: str, text: str) -> bool:
    pattern = rf"(?<![A-Za-z0-9.+#]){re.escape(skill)}(?![A-Za-z0-9.+#])"
    return re.search(pattern, text, re.I) is not None


def _is_long(text: str) -> bool:
    words = text.split()
    return len(words) >= 10 or (text.rstrip().endswith((".", "!", "?")) and len(words) >= 6)


def _add(bucket: list[str], seen: set[str], display: str, cap: int) -> None:
    if len(bucket) >= cap:
        return
    cleaned = " ".join(display.split()).strip(" .-")
    key = normalize_key(cleaned)
    if len(key) < 2 or key in seen:
        return
    seen.add(key)
    bucket.append(cleaned[:80])


def _merge(*groups: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for item in group:
            key = normalize_key(item)
            if key in seen:
                continue
            seen.add(key)
            merged.append(item)
            if len(merged) >= KEYWORD_CAP:
                return merged
    return merged


def _empty(title: str, company: str, reason: str) -> dict:
    return {
        "title": title,
        "company": company,
        "required": [],
        "preferred": [],
        "keywords": [],
        "blockedReason": reason,
    }

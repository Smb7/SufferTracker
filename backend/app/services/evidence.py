"""Citable career evidence derived from ``career_context``.

Interests and next-job goals stay under ``targeting``. They are not evidence
and must not be scored as qualifications.
"""

import re

from app.models import CareerProfile
from app.services.onboarding import career_context

SKILL_CAP = 60
EXPERIENCE_TERM_CAP = 60
EDUCATION_TERM_CAP = 45
ROLE_CAP = 20
INTEREST_CAP = 40
TARGET_ROLE_CAP = 12

_STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "to", "for", "with", "in", "on", "at", "from", "by", "as",
    "into", "over", "after", "before", "about", "across", "than", "then", "that", "this", "these",
    "those", "their", "our", "your", "its", "be", "is", "are", "was", "were", "been", "being",
    "have", "has", "had", "do", "does", "did", "not", "no", "nor", "but", "if", "so", "such", "per",
    "via", "using", "used", "use", "including", "include", "includes", "i", "we", "my", "me", "our",
    "also", "plus", "daily", "weekly", "often", "regularly", "primarily", "mainly",
}
_COMMON_CAPS = {
    "january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
    "november", "december", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "remote", "hybrid", "onsite", "senior", "junior", "lead", "staff", "principal", "associate",
    "english", "spanish", "french", "german", "inc", "llc", "ltd", "corp",
}
# Distinctive tools and credentials. A boost for lowercase mentions, not a skill dictionary.
_LEXICON = {
    "python", "sql", "excel", "epic", "cerner", "figma", "react", "angular", "typescript", "javascript",
    "postgres", "postgresql", "docker", "kubernetes", "aws", "azure", "gcp", "java", "golang", "rust",
    "terraform", "graphql", "salesforce", "jira", "tableau", "sap", "quickbooks", "photoshop",
    "illustrator", "hipaa", "cpr", "acls", "bls", "ehr", "nodejs", "node.js", "c#", "c++", ".net",
    "pandas", "django", "fastapi", "vue", "kotlin", "swift", "php", "ruby", "mongodb", "redis",
    "snowflake", "linux", "git", "github", "gitlab", "ci/cd", "rest", "html", "css", "matlab", "spss",
    "autocad", "workday", "hubspot", "zendesk", "powerbi", "sketch", "indesign",
}

_CUE = re.compile(
    r"\b(?:using|used|use|including|includes|include|via|tools?|skills?|technologies|software|platforms?|with)\b\s*[:\-]?\s*([^.;\n]{1,100})",
    re.I,
)
_QUOTED = re.compile(r"[\"“]([^\"”]{2,60})[\"”]")
_PAREN = re.compile(r"\(([^)]{2,80})\)")
_TOKEN = re.compile(r"[.]?[A-Za-z][\w#+./+-]{0,40}")
_LIST_SEP = re.compile(r"[,;\n•|/]|\band\b", re.I)
_TAIL = re.compile(r"\b(?:for|to|that|which|while|during|where|who|when|because)\b", re.I)


def normalize_key(value: str) -> str:
    """Case-fold and strip punctuation without destroying tokens like C# or node.js."""
    text = value.casefold().replace("&", " and ")
    text = text.replace("'", "").replace("’", "")
    text = re.sub(r"\b([a-z])\.(?=[a-z])", r"\1", text)
    text = re.sub(r"(?<=[a-z])\.(?=[a-z]\b)", "", text)
    text = re.sub(r"[^\w\s#+./+-]", " ", text)
    text = text.replace("_", " ")
    text = re.sub(r"\s+", " ", text).strip(" .-")
    return text


def career_evidence(profile: CareerProfile) -> dict:
    """Evidence a later scorer can cite. Built only from ``career_context``."""
    return evidence_from_context(career_context(profile))


def evidence_from_context(context: dict) -> dict:
    skills = _skill_terms(list(context.get("skills") or []))
    roles, experience_terms = _experience(list(context.get("experience") or []))
    education_terms = _education_terms(list(context.get("education") or []))
    goals = context.get("goals") if isinstance(context.get("goals"), dict) else {}
    return {
        "skills": skills,
        "experienceTerms": experience_terms,
        "educationTerms": education_terms,
        "roles": roles,
        "targeting": {
            "interests": _clean_display_list(list(context.get("interests") or []), INTEREST_CAP),
            "targetRoles": _clean_display_list(list(goals.get("targetRoles") or []), TARGET_ROLE_CAP),
            "narrative": str(goals.get("narrative") or ""),
            "industries": _clean_display_list(list(goals.get("industries") or []), TARGET_ROLE_CAP),
            "locations": _clean_display_list(list(goals.get("locations") or []), TARGET_ROLE_CAP),
            "workStyle": str(goals.get("workStyle") or ""),
            "compensation": str(goals.get("compensation") or ""),
            "timeline": str(goals.get("timeline") or ""),
            "constraints": str(goals.get("constraints") or ""),
        },
    }


def source_for(evidence: dict, term: str) -> str | None:
    """Where a term came from: skill, experience, or education. Never targeting."""
    found = find_term(evidence, term)
    return None if found is None else found["source"]


def find_term(evidence: dict, term: str) -> dict | None:
    key = normalize_key(term)
    if not key:
        return None
    exact = _match(evidence, key, exact=True)
    if exact is not None:
        return exact
    return _match(evidence, key, exact=False)


def has_scoreable_evidence(evidence: dict) -> bool:
    return bool(evidence.get("skills") or evidence.get("experienceTerms"))


def _match(evidence: dict, key: str, *, exact: bool) -> dict | None:
    for bucket in ("skills", "experienceTerms", "educationTerms"):
        for item in evidence.get(bucket) or []:
            item_key = item.get("key") or ""
            if exact and item_key == key:
                return item
            if not exact and _contains_term(item_key, key):
                return item
    return None


def _contains_term(haystack: str, needle: str) -> bool:
    if not haystack or not needle or haystack == needle or len(needle) < 4:
        return False
    return f" {needle} " in f" {haystack} "


def _skill_terms(skills: list) -> list[dict]:
    terms: list[dict] = []
    seen: set[str] = set()
    for raw in skills:
        if not isinstance(raw, str):
            continue
        for display in _list_parts(raw) or ([raw.strip()] if raw.strip() and not _is_sentence(raw) else []):
            _add(terms, seen, display, "skill", field="skill", cap=SKILL_CAP)
    for index, item in enumerate(terms):
        item["id"] = f"skill:{index}"
    return terms


def _experience(items: list) -> tuple[list[dict], list[dict]]:
    roles: list[dict] = []
    terms: list[dict] = []
    seen: set[str] = set()
    for index, item in enumerate(items[:ROLE_CAP]):
        if not isinstance(item, dict):
            continue
        role = {
            "id": index,
            "title": str(item.get("title") or ""),
            "company": str(item.get("company") or ""),
            "start": str(item.get("start") or ""),
            "end": str(item.get("end") or ""),
            "highlights": str(item.get("highlights") or ""),
        }
        roles.append(role)
        if role["title"]:
            _add(terms, seen, role["title"], "experience", role_id=index, field="title", cap=EXPERIENCE_TERM_CAP)
            for token in _content_tokens(role["title"]):
                _add(terms, seen, token, "experience", role_id=index, field="title", cap=EXPERIENCE_TERM_CAP)
        if role["company"]:
            _add(terms, seen, role["company"], "experience", role_id=index, field="company", cap=EXPERIENCE_TERM_CAP)
        for display in _text_terms(role["highlights"]):
            _add(terms, seen, display, "experience", role_id=index, field="highlights", cap=EXPERIENCE_TERM_CAP)
    return roles, terms


def _education_terms(items: list) -> list[dict]:
    terms: list[dict] = []
    seen: set[str] = set()
    for index, item in enumerate(items[:15]):
        if not isinstance(item, dict):
            continue
        for field in ("credential", "field", "institution"):
            raw = str(item.get(field) or "").strip()
            if not raw:
                continue
            parts = _list_parts(raw) if _has_list_sep(raw) and not _is_sentence(raw) else [raw]
            for display in parts:
                _add(terms, seen, display, "education", role_id=index, field=field, cap=EDUCATION_TERM_CAP)
            if field == "field":
                for token in _content_tokens(raw):
                    _add(terms, seen, token, "education", role_id=index, field=field, cap=EDUCATION_TERM_CAP)
    return terms


def _add(
    terms: list[dict],
    seen: set[str],
    display: str,
    source: str,
    *,
    role_id: int | None = None,
    field: str,
    cap: int,
) -> None:
    if len(terms) >= cap:
        return
    cleaned = " ".join(display.split()).strip(" .-")
    key = normalize_key(cleaned)
    if len(key) < 2 or key in seen or key in _STOPWORDS:
        return
    seen.add(key)
    item = {"id": _term_id(source, role_id, field, key), "key": key, "display": cleaned[:80], "source": source, "field": field}
    if role_id is not None:
        item["roleId"] = role_id
    terms.append(item)


def _term_id(source: str, role_id: int | None, field: str, key: str) -> str:
    if source == "skill":
        return f"skill:{key}"
    owner = role_id if role_id is not None else 0
    return f"{source}:{owner}:{field}:{key}"


def _text_terms(text: str) -> list[str]:
    raw = text.strip()
    if not raw:
        return []
    if not _is_sentence(raw):
        return _list_parts(raw) or [raw]
    found: list[str] = []
    for match in _QUOTED.finditer(raw):
        found.extend(_list_parts(match.group(1)) or [match.group(1).strip()])
    for match in _PAREN.finditer(raw):
        inner = match.group(1)
        if _has_list_sep(inner) or len(inner.split()) <= 4:
            found.extend(_list_parts(inner) or [inner.strip()])
    for match in _CUE.finditer(raw):
        chunk = _TAIL.split(match.group(1), maxsplit=1)[0]
        if _has_list_sep(chunk) or len(chunk.split()) <= 3:
            found.extend(_list_parts(chunk))
    for sentence in re.split(r"(?<=[.!?])\s+", raw):
        tokens = [_clean_token(token) for token in _TOKEN.findall(sentence)]
        tokens = [token for token in tokens if token]
        for index, token in enumerate(tokens):
            if index == 0 or not _is_toolish(token):
                continue
            found.append(token)
    return found


def _list_parts(text: str) -> list[str]:
    if not text or not text.strip() or not _has_list_sep(text):
        return []
    parts: list[str] = []
    for part in _LIST_SEP.split(text):
        words = part.strip(" .:-•*").split()
        while words and words[0].casefold().strip(".,") in _STOPWORDS:
            words.pop(0)
        while words and words[-1].casefold().strip(".,") in _STOPWORDS:
            words.pop()
        if not words or len(words) > 6:
            continue
        cleaned = " ".join(words).strip(" .-")
        if cleaned:
            parts.append(cleaned)
    return parts


def _content_tokens(text: str) -> list[str]:
    tokens = []
    for token in _TOKEN.findall(text):
        key = normalize_key(token)
        if len(key) < 3 or key in _STOPWORDS or key in _COMMON_CAPS:
            continue
        tokens.append(token)
    return tokens


def _is_sentence(text: str) -> bool:
    words = text.split()
    if len(words) >= 8:
        return True
    if text.rstrip().endswith((".", "!", "?")) and len(words) >= 5:
        return True
    return False


def _has_list_sep(text: str) -> bool:
    return bool(_LIST_SEP.search(text))


def distinctive_tokens(text: str) -> list[str]:
    """Tool-shaped tokens in prose. Bare title-case words are not tools."""
    found: list[str] = []
    seen: set[str] = set()
    for token in _TOKEN.findall(text):
        cleaned = _clean_token(token)
        if not cleaned or not _is_distinctive(cleaned):
            continue
        key = normalize_key(cleaned)
        if len(key) < 2 or key in seen:
            continue
        seen.add(key)
        found.append(cleaned)
    return found


def _clean_token(token: str) -> str:
    return token.strip(".,;:!?()[]\"'")


def _is_distinctive(token: str) -> bool:
    token = _clean_token(token)
    key = normalize_key(token)
    if len(key) < 2 or key in _STOPWORDS or key in _COMMON_CAPS:
        return False
    if any(char.isdigit() or char in "#+/" for char in token) or "." in token:
        return True
    if any(char.isupper() for char in token[1:]):
        return True
    if token.isupper() and len(token) <= 8:
        return True
    return key in _LEXICON


def _is_toolish(token: str) -> bool:
    token = _clean_token(token)
    key = normalize_key(token)
    if len(key) < 2 or key in _STOPWORDS or key in _COMMON_CAPS:
        return False
    if any(char.isdigit() or char in "#+/" for char in token) or ("." in token and not token.startswith(".")):
        return True
    if any(char.isupper() for char in token[1:]):
        return True
    if token.isupper() and len(token) <= 8:
        return True
    if key in _LEXICON:
        return True
    return bool(token[:1].isupper() and token[1:].islower() and len(token) >= 3)


def _clean_display_list(values: list, limit: int) -> list[str]:
    items: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            continue
        item = " ".join(value.split()).strip()
        key = item.casefold()
        if len(item) < 2 or key in seen:
            continue
        seen.add(key)
        items.append(item[:80])
        if len(items) >= limit:
            break
    return items

"""Tailored resume for one job. Every claim stays tied to career evidence.

A configured model may rewrite wording. It cannot add employers, dates, tools,
or degrees, and it does not pick the fit score. With no OpenCode connection
and no AI endpoint, the deterministic draft is the resume.
"""

import json
import re
from dataclasses import dataclass

import httpx

from app.config import Settings, get_settings
from app.services.ai import AiProviderError, AiTarget, complete_chat, model_ready
from app.services.opencode import complete_opencode
from app.services.evidence import distinctive_tokens, find_term, normalize_key
from app.services.fit import score_fit

EDIT_REJECTED = "That edit adds an employer, date, tool, or credential that is not in your evidence."
UNTIED = "That edit is not tied to your evidence."

_YEAR = re.compile(r"\b(?:19|20)\d{2}\b")
_DEGREE = re.compile(
    r"(?i)(?<![A-Za-z])(ph\.?d\.?|m\.?s\.?|m\.?a\.?|b\.?s\.?|b\.?a\.?|"
    r"bachelor(?:'s)?|master(?:'s)?|associate(?:'s)?|doctorate)(?![A-Za-z])"
)
_NAMED = re.compile(r"[A-Za-z][\w'+./#-]*")
_START_OK = {
    "led", "built", "shipped", "developed", "designed", "managed", "created", "owned", "ran",
    "supported", "maintained", "improved", "delivered", "wrote", "implemented", "coordinated",
    "helped", "worked", "used", "using", "including", "the", "a", "an", "and", "for", "with",
    "from", "to", "in", "on", "of", "our", "my", "i", "we", "this", "that", "their", "also",
    "plus", "senior", "junior", "responsible", "experienced", "proficient", "matched",
}
_MONTHS = {
    "january", "february", "march", "april", "may", "june", "july", "august", "september",
    "october", "november", "december",
}


class ResumeEditError(Exception):
    """A reviewed edit introduced a claim the evidence does not support."""


@dataclass
class Catalog:
    tokens: set[str]
    years: set[str]
    credential_blob: str
    skill_ids: set[str]
    role_term_ids: dict[int, set[str]]
    education: dict[str, dict]


def generate_resume(
    evidence: dict,
    requirements: dict,
    *,
    education: list | None = None,
    settings: Settings | None = None,
    client: httpx.Client | None = None,
    target: AiTarget | None = None,
) -> dict:
    """Draft or blocked result. Does not persist. Does not log career text."""
    education = [item for item in (education or []) if isinstance(item, dict)]
    fit = score_fit(evidence, requirements)
    if fit["score"] is None:
        return {
            "blockedReason": fit["blockedReason"],
            "profileBlocked": fit["profileBlocked"],
            "score": None,
            "missing": [],
            "sections": None,
            "evidenceIds": [],
        }
    catalog = build_catalog(evidence, education)
    sections = _deterministic(evidence, fit, education)
    settings = settings or get_settings()
    if model_ready(settings, target):
        sections = _rewrite(sections, evidence, fit, education, settings, client, catalog, target)
    return {
        "blockedReason": None,
        "profileBlocked": False,
        "score": fit["score"],
        "missing": list(fit["missing"]),
        "sections": sections,
        "evidenceIds": evidence_ids(sections),
    }


def accept_edits(sections: dict, evidence: dict, education: list | None = None) -> dict:
    """Return a new sections dict, or raise if an edit is not tied to evidence."""
    education = [item for item in (education or []) if isinstance(item, dict)]
    catalog = build_catalog(evidence, education)
    roles = {role["id"]: role for role in evidence.get("roles") or [] if isinstance(role, dict)}
    summary = str(sections.get("summary") or "").strip()
    if claim_problem(summary, catalog):
        raise ResumeEditError(EDIT_REJECTED)

    skills = []
    for item in sections.get("skills") or []:
        if not isinstance(item, dict):
            raise ResumeEditError(UNTIED)
        evidence_id = str(item.get("evidenceId") or "")
        if evidence_id not in catalog.skill_ids:
            raise ResumeEditError(UNTIED)
        text = str(item.get("text") or "").strip()
        if claim_problem(text, catalog):
            raise ResumeEditError(EDIT_REJECTED)
        skills.append({"evidenceId": evidence_id, "text": text})

    experience = []
    for item in sections.get("experience") or []:
        if not isinstance(item, dict):
            raise ResumeEditError(UNTIED)
        role_id = _as_int(item.get("roleId"))
        role = roles.get(role_id) if role_id is not None else None
        if role is None:
            raise ResumeEditError(UNTIED)
        if not _same(item.get("title"), role.get("title")) or not _same(item.get("company"), role.get("company")):
            raise ResumeEditError(EDIT_REJECTED)
        if not _same(item.get("start"), role.get("start")) or not _same(item.get("end"), role.get("end")):
            raise ResumeEditError(EDIT_REJECTED)
        bullets = []
        allowed = catalog.role_term_ids.get(role_id, set())
        for bullet in item.get("bullets") or []:
            if not isinstance(bullet, dict):
                raise ResumeEditError(UNTIED)
            evidence_id = str(bullet.get("evidenceId") or "")
            if evidence_id not in allowed:
                raise ResumeEditError(UNTIED)
            text = str(bullet.get("text") or "").strip()
            if claim_problem(text, catalog):
                raise ResumeEditError(EDIT_REJECTED)
            bullets.append({"evidenceId": evidence_id, "text": text})
        experience.append({
            "roleId": role_id,
            "title": str(role.get("title") or ""),
            "company": str(role.get("company") or ""),
            "start": str(role.get("start") or ""),
            "end": str(role.get("end") or ""),
            "bullets": bullets,
        })

    education_out = []
    for item in sections.get("education") or []:
        if not isinstance(item, dict):
            raise ResumeEditError(UNTIED)
        evidence_id = str(item.get("evidenceId") or "")
        recorded = catalog.education.get(evidence_id)
        if recorded is None:
            raise ResumeEditError(UNTIED)
        for field in ("institution", "credential", "field", "year"):
            if not _same(item.get(field), recorded.get(field)):
                raise ResumeEditError(EDIT_REJECTED)
        text = str(item.get("text") or "").strip()
        if claim_problem(text, catalog):
            raise ResumeEditError(EDIT_REJECTED)
        education_out.append({
            "evidenceId": evidence_id,
            "institution": recorded["institution"],
            "credential": recorded["credential"],
            "field": recorded["field"],
            "year": recorded["year"],
            "text": text,
        })
    return {"summary": summary, "skills": skills, "experience": experience, "education": education_out}


def evidence_ids(sections: dict) -> list[str]:
    found: list[str] = []
    for skill in sections.get("skills") or []:
        if skill.get("evidenceId"):
            found.append(skill["evidenceId"])
    for role in sections.get("experience") or []:
        for bullet in role.get("bullets") or []:
            if bullet.get("evidenceId"):
                found.append(bullet["evidenceId"])
    for item in sections.get("education") or []:
        if item.get("evidenceId"):
            found.append(item["evidenceId"])
    return found


def build_catalog(evidence: dict, education: list) -> Catalog:
    tokens: set[str] = set()
    years: set[str] = set()
    for bucket in ("skills", "experienceTerms", "educationTerms"):
        for item in evidence.get(bucket) or []:
            if isinstance(item, dict):
                _add_text(tokens, years, item.get("display") or "")
                _add_text(tokens, years, item.get("key") or "")
    for role in evidence.get("roles") or []:
        if not isinstance(role, dict):
            continue
        for field in ("title", "company", "start", "end", "highlights"):
            _add_text(tokens, years, role.get(field) or "")
    credential_parts: list[str] = []
    for item in education:
        for field in ("institution", "credential", "field", "year", "notes"):
            _add_text(tokens, years, item.get(field) or "")
        credential_parts.extend(str(item.get(field) or "") for field in ("credential", "field", "notes"))
    skill_ids = {item["id"] for item in evidence.get("skills") or [] if isinstance(item, dict) and item.get("id")}
    role_term_ids: dict[int, set[str]] = {}
    for item in evidence.get("experienceTerms") or []:
        if not isinstance(item, dict) or not isinstance(item.get("roleId"), int) or not item.get("id"):
            continue
        role_term_ids.setdefault(item["roleId"], set()).add(item["id"])
    recorded = {item["evidenceId"]: item for item in _recorded_education(evidence, education)}
    return Catalog(tokens, years, " ".join(credential_parts), skill_ids, role_term_ids, recorded)


def claim_problem(text: str, catalog: Catalog) -> str | None:
    """None when the text adds no employer, date, tool, or degree outside the catalog."""
    cleaned = " ".join(text.split()).strip()
    if not cleaned:
        return None
    if len(cleaned) > 4000:
        return "length"
    for year in _YEAR.findall(cleaned):
        if year not in catalog.years:
            return "date"
    compact_blob = re.sub(r"[^a-z0-9]", "", catalog.credential_blob.casefold())
    for match in _DEGREE.finditer(cleaned):
        compact = re.sub(r"[^a-z0-9]", "", match.group(1).casefold())
        if compact and compact not in compact_blob:
            return "credential"
    for token in distinctive_tokens(cleaned):
        if normalize_key(token) not in catalog.tokens:
            return "tool"
    for word in _NAMED.findall(cleaned):
        if not any(char.isupper() for char in word):
            continue
        key = normalize_key(word)
        if not key or key in catalog.tokens or key in _MONTHS or key in _START_OK:
            continue
        return "employer"
    return None


def _deterministic(evidence: dict, fit: dict, education: list) -> dict:
    matched = _matched_keys(evidence, fit)
    return {
        "summary": _summary(evidence, fit),
        "skills": _skills(evidence, matched),
        "experience": _experience(evidence, matched),
        "education": _education_sections(evidence, education, matched),
    }


def _rewrite(
    sections: dict,
    evidence: dict,
    fit: dict,
    education: list,
    settings: Settings,
    client: httpx.Client | None,
    catalog: Catalog,
    target: AiTarget | None = None,
) -> dict:
    messages = [
        {"role": "system", "content": _system(evidence, fit, education)},
        {"role": "user", "content": "Return the resume JSON."},
    ]
    try:
        if target is not None and target.kind == "opencode":
            result = complete_opencode(messages, target.model_id, target.api_key, client)
        else:
            result = complete_chat(messages, settings, client)
    except AiProviderError:
        return sections
    parsed = _parse_payload(result.content)
    if not parsed:
        return sections
    return _merge(sections, parsed, catalog)


def _system(evidence: dict, fit: dict, education: list) -> str:
    packet = {
        "skills": evidence.get("skills") or [],
        "experienceTerms": evidence.get("experienceTerms") or [],
        "educationTerms": evidence.get("educationTerms") or [],
        "roles": evidence.get("roles") or [],
        "education": [
            {key: str(item.get(key) or "") for key in ("institution", "credential", "field", "year", "notes")}
            for item in education
        ],
    }
    fit_packet = {"matched": fit.get("matched") or [], "missing": fit.get("missing") or []}
    return (
        "Rewrite resume bullets for clarity and keyword alignment.\n"
        "Rules:\n"
        "- Use only Evidence JSON. Do not add employers, dates, tools, or degrees that are absent from it.\n"
        "- Every bullet needs an evidenceId copied from Evidence JSON. Drop anything you cannot tie to one.\n"
        "- Missing terms are gaps. Do not write bullets for them.\n"
        "- Do not change employers, titles, or dates.\n"
        "- Return only JSON with keys summary, skills, experience, education.\n"
        "- skills: [{evidenceId, text}]. experience: [{roleId, bullets: [{evidenceId, text}]}]. "
        "education: [{evidenceId, text}].\n"
        f"Evidence JSON:\n{json.dumps(packet, ensure_ascii=False)}\n"
        f"Fit JSON:\n{json.dumps(fit_packet, ensure_ascii=False)}"
    )


def _merge(base: dict, model: dict, catalog: Catalog) -> dict:
    skill_text = _accepted_text(model.get("skills"), catalog)
    experience = []
    for role in base["experience"]:
        proposed = _model_role(model, role["roleId"])
        bullet_text = _accepted_text((proposed or {}).get("bullets"), catalog)
        bullets = []
        for bullet in role["bullets"]:
            text = bullet_text.get(bullet["evidenceId"], bullet["text"])
            bullets.append({"evidenceId": bullet["evidenceId"], "text": text})
        experience.append({**role, "bullets": bullets})
    education_text = _accepted_text(model.get("education"), catalog)
    education = []
    for item in base["education"]:
        text = education_text.get(item["evidenceId"], item["text"])
        education.append({**item, "text": text})
    summary = base["summary"]
    candidate = str(model.get("summary") or "").strip()
    if candidate and not claim_problem(candidate, catalog):
        summary = candidate[:4000]
    return {"summary": summary, "skills": _replaced(base["skills"], skill_text), "experience": experience, "education": education}


def _accepted_text(items: object, catalog: Catalog) -> dict[str, str]:
    accepted: dict[str, str] = {}
    if not isinstance(items, list):
        return accepted
    for item in items:
        if not isinstance(item, dict):
            continue
        evidence_id = str(item.get("evidenceId") or item.get("evidence_id") or "")
        text = str(item.get("text") or "").strip()
        if not evidence_id or not text or claim_problem(text, catalog):
            continue
        accepted.setdefault(evidence_id, text[:4000])
    return accepted


def _replaced(items: list[dict], texts: dict[str, str]) -> list[dict]:
    return [{"evidenceId": item["evidenceId"], "text": texts.get(item["evidenceId"], item["text"])} for item in items]


def _model_role(model: dict, role_id: int) -> dict | None:
    for item in model.get("experience") or []:
        if isinstance(item, dict) and _as_int(item.get("roleId", item.get("role_id"))) == role_id:
            return item
    return None


def _matched_keys(evidence: dict, fit: dict) -> set[str]:
    keys: set[str] = set()
    for item in fit.get("matched") or []:
        if not isinstance(item, dict):
            continue
        found = find_term(evidence, str(item.get("term") or ""))
        if found:
            keys.add(found["key"])
    return keys


def _summary(evidence: dict, fit: dict) -> str:
    names: list[str] = []
    seen: set[str] = set()
    for item in fit.get("matched") or []:
        if not isinstance(item, dict):
            continue
        found = find_term(evidence, str(item.get("term") or ""))
        display = found["display"] if found else str(item.get("term") or "")
        key = normalize_key(display)
        if not key or key in seen:
            continue
        seen.add(key)
        names.append(display)
    return ", ".join(names[:12])


def _skills(evidence: dict, matched: set[str]) -> list[dict]:
    skills = [item for item in evidence.get("skills") or [] if isinstance(item, dict) and item.get("id")]
    ordered = sorted(skills, key=lambda item: 0 if item.get("key") in matched else 1)
    return [{"evidenceId": item["id"], "text": item["display"]} for item in ordered]


def _experience(evidence: dict, matched: set[str]) -> list[dict]:
    roles = [role for role in evidence.get("roles") or [] if isinstance(role, dict)]
    terms = [item for item in evidence.get("experienceTerms") or [] if isinstance(item, dict)]

    def hits(role: dict) -> int:
        return sum(1 for term in terms if term.get("roleId") == role.get("id") and term.get("key") in matched)

    sections = []
    for role in sorted(roles, key=lambda item: -hits(item)):
        if not any(str(role.get(field) or "").strip() for field in ("title", "company", "highlights")):
            continue
        bullet = _bullet(role, terms)
        sections.append({
            "roleId": role.get("id"),
            "title": str(role.get("title") or ""),
            "company": str(role.get("company") or ""),
            "start": str(role.get("start") or ""),
            "end": str(role.get("end") or ""),
            "bullets": [bullet] if bullet else [],
        })
    return sections


def _bullet(role: dict, terms: list[dict]) -> dict | None:
    highlights = " ".join(str(role.get("highlights") or "").split()).strip()
    if not highlights:
        return None
    role_terms = [term for term in terms if term.get("roleId") == role.get("id") and term.get("id")]
    highlight_terms = [term for term in role_terms if term.get("field") == "highlights"]
    chosen = highlight_terms or role_terms
    if not chosen:
        return None
    return {"evidenceId": chosen[0]["id"], "text": highlights}


def _education_sections(evidence: dict, education: list, matched: set[str]) -> list[dict]:
    items = _recorded_education(evidence, education)
    terms = evidence.get("educationTerms") or []
    matched_indexes = {term.get("roleId") for term in terms if isinstance(term, dict) and term.get("key") in matched}
    items.sort(key=lambda item: 0 if item["roleId"] in matched_indexes else 1)
    return [
        {
            "evidenceId": item["evidenceId"],
            "institution": item["institution"],
            "credential": item["credential"],
            "field": item["field"],
            "year": item["year"],
            "text": _education_text(item),
        }
        for item in items
    ]


def _recorded_education(evidence: dict, education: list) -> list[dict]:
    terms = [item for item in evidence.get("educationTerms") or [] if isinstance(item, dict)]
    recorded = []
    for index, raw in enumerate(education):
        evidence_id = _education_evidence_id(index, terms)
        if not evidence_id:
            continue
        item = {
            "roleId": index,
            "evidenceId": evidence_id,
            "institution": str(raw.get("institution") or ""),
            "credential": str(raw.get("credential") or ""),
            "field": str(raw.get("field") or ""),
            "year": str(raw.get("year") or ""),
            "notes": str(raw.get("notes") or ""),
        }
        if any(item[field].strip() for field in ("institution", "credential", "field", "year", "notes")):
            recorded.append(item)
    return recorded


def _education_evidence_id(index: int, terms: list[dict]) -> str | None:
    for field in ("credential", "institution", "field"):
        for term in terms:
            if term.get("roleId") == index and term.get("field") == field and term.get("id"):
                return term["id"]
    for term in terms:
        if term.get("roleId") == index and term.get("id"):
            return term["id"]
    return None


def _education_text(item: dict) -> str:
    parts = [item["credential"], item["field"], item["institution"], item["year"], item["notes"]]
    return ", ".join(part.strip() for part in parts if part and part.strip())


def _add_text(tokens: set[str], years: set[str], value: object) -> None:
    cleaned = " ".join(str(value).split()).strip()
    if not cleaned:
        return
    key = normalize_key(cleaned)
    if key:
        tokens.add(key)
    years.update(_YEAR.findall(cleaned))
    for word in _NAMED.findall(cleaned):
        word_key = normalize_key(word)
        if word_key:
            tokens.add(word_key)


def _same(left: object, right: object) -> bool:
    return " ".join(str(left or "").split()).casefold() == " ".join(str(right or "").split()).casefold()


def _as_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _parse_payload(content: str) -> dict | None:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return data if isinstance(data, dict) else None

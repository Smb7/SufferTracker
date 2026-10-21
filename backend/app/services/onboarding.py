"""Career onboarding for later SufferTracker agents.

`career_context` is the stable blob future coaching should read. It holds only
what the user told us: experience, education, skills, interests, and next-job
goals. The interviewer fills that blob. A configured chat model may structure
the turns; otherwise the guided interviewer does, and nothing leaves the API.
"""

import json
import logging
import re
from dataclasses import dataclass

import httpx

from app.config import Settings, get_settings
from app.models import CareerProfile
from app.services.ai import AiProviderError, AiTarget, complete_chat, model_ready
from app.services.opencode import complete_opencode

logger = logging.getLogger(__name__)

SECTIONS = ("experience", "education", "skills", "interests", "goals")
OPENING = (
    "I'm the coach for this workspace. Before I can help later, I need a working picture of you — "
    "experience, education, skills, interests, and the job you want next.\n\n"
    "Short answers are enough. Correct me whenever I get something wrong.\n\n"
    "What have you been doing for work? Roles, companies, freelance, projects, or a gap all count. Say none if that doesn't apply."
)
QUESTIONS = {
    "experience": "What have you been doing for work? Roles, companies, freelance, projects, or a gap all count. Say none if that doesn't apply.",
    "education": "What about education — degrees, bootcamps, certificates, or a self-taught path? Say none if that doesn't apply.",
    "skills": "Which skills should I treat as yours? Languages, tools, methods, or domain knowledge — the ones you'd stand behind in an interview.",
    "interests": "What kind of problems or work actually interest you, beyond a job title?",
    "goals": "What should the next job look like? Role, company type, location or remote, pay if you have a number, and anything that is a must or a no.",
}
_CONFIRM = {
    "yes", "yep", "yeah", "yup", "correct", "confirmed", "confirm", "looks good", "looks right",
    "thats right", "thats correct", "thats me", "save it", "save", "all good", "good", "ok",
    "okay", "sure", "sounds good", "sounds right", "done", "that's it", "thats it",
}
_NONE = {
    "none", "n a", "na", "skip", "skip this", "pass", "nothing", "no", "nope", "not applicable",
    "doesnt apply", "no experience", "no work experience", "no formal education", "no education",
    "no degree", "i have none", "i dont have any", "not really", "no formal",
}
_CREDENTIALS = (
    ("ph.d", "Ph.D."), ("phd", "Ph.D."), ("doctorate", "Doctorate"), ("mba", "MBA"),
    ("master", "Master's"), ("bachelor", "Bachelor's"), ("associate", "Associate"),
    ("bootcamp", "Bootcamp"), ("certification", "Certification"), ("certificate", "Certificate"),
    ("diploma", "Diploma"), ("b.s", "B.S."), ("b.a", "B.A."), ("m.s", "M.S."), ("m.a", "M.A."),
    ("bsc", "B.S."), ("ba", "B.A."), ("ms", "M.S."), ("ma", "M.A."),
)
_ROLE_PATTERNS = (
    r"(?:looking for|searching for|targeting|applying for) (?:an? |the )?(.+)",
    r"(?:want to be|want to become|next role is|next job is|next job as) (?:an? )?(.+)",
    r"(?:role as) (?:an? )?(.+)",
)


@dataclass(frozen=True)
class TurnResult:
    reply: str
    provider: str
    notice: str
    completed: bool


def empty_goals() -> dict:
    return {
        "targetRoles": [],
        "industries": [],
        "locations": [],
        "workStyle": "",
        "compensation": "",
        "timeline": "",
        "narrative": "",
        "constraints": "",
    }


def career_context(profile: CareerProfile) -> dict:
    """Context later agents should read. Does not include chat or provider notes."""
    return {
        "status": profile.status,
        "summary": profile.summary or "",
        "experience": list(profile.experience or []),
        "education": list(profile.education or []),
        "skills": list(profile.skills or []),
        "interests": list(profile.interests or []),
        "goals": {**empty_goals(), **(profile.goals or {})},
        "missing": missing_sections(profile),
    }


def missing_sections(profile: CareerProfile) -> list[str]:
    acknowledged = profile.acknowledged or {}
    missing: list[str] = []
    if not profile.experience and not acknowledged.get("experience"):
        missing.append("experience")
    if not profile.education and not acknowledged.get("education"):
        missing.append("education")
    if not profile.skills:
        missing.append("skills")
    if not profile.interests:
        missing.append("interests")
    goals = profile.goals or {}
    narrative = str(goals.get("narrative") or "").strip()
    roles = goals.get("targetRoles") or []
    if len(narrative) < 12 and not roles:
        missing.append("goals")
    return missing


def apply_user_turn(
    profile: CareerProfile,
    content: str,
    history: list[tuple[str, str]] | None = None,
    settings: Settings | None = None,
    client: httpx.Client | None = None,
    target: AiTarget | None = None,
) -> TurnResult:
    settings = settings or get_settings()
    text = content.strip()
    before = missing_sections(profile)
    if not before and _is_confirm(text):
        refresh_summary(profile)
        return TurnResult(_saved_reply(), profile.provider or "guided", "", True)
    if model_ready(settings, target):
        try:
            return _model_turn(profile, text, history or [], settings, client, target)
        except (AiProviderError, ValueError, json.JSONDecodeError):
            logger.info("Onboarding model turn failed; using the guided interviewer.")
            reply = _guided_turn(profile, text, before)
            notice = "The model could not answer, so the guided interviewer handled this turn."
            if target is not None and target.notice:
                notice = target.notice
            return TurnResult(reply, "guided", notice, False)
    notice = target.notice if target is not None else ""
    return TurnResult(_guided_turn(profile, text, before), "guided", notice, False)


def apply_context_update(
    profile: CareerProfile,
    *,
    summary: str | None = None,
    experience: list[dict] | None = None,
    education: list[dict] | None = None,
    skills: list[str] | None = None,
    interests: list[str] | None = None,
    goals: dict | None = None,
) -> None:
    if experience is not None:
        profile.experience = _clean_items(experience, _clean_experience, 20)
        if profile.experience:
            _clear_ack(profile, "experience")
    if education is not None:
        profile.education = _clean_items(education, _clean_education, 15)
        if profile.education:
            _clear_ack(profile, "education")
    if skills is not None:
        profile.skills = _clean_terms(skills, 60)
    if interests is not None:
        profile.interests = _clean_terms(interests, 40)
    if goals is not None:
        profile.goals = _full_goals(goals)
    if summary is None:
        refresh_summary(profile)
    else:
        profile.summary = _clip(summary, 4000)
    if profile.status == "completed" and missing_sections(profile):
        profile.status = "in_progress"
        profile.completed_at = None
    elif profile.status == "not_started" and _has_any(profile):
        profile.status = "in_progress"


def refresh_summary(profile: CareerProfile) -> None:
    sentences: list[str] = []
    if profile.experience:
        bits = []
        for item in profile.experience[:4]:
            title = item.get("title") or ""
            company = item.get("company") or ""
            if title and company:
                bits.append(f"{title} at {company}")
            elif title or company:
                bits.append(title or company)
        sentences.append("Experience includes " + "; ".join(bits) + "." if bits else "Experience was described in their own words.")
    elif (profile.acknowledged or {}).get("experience"):
        sentences.append("They reported no formal work experience.")
    if profile.education:
        first = profile.education[0]
        label = " ".join(
            part for part in (
                first.get("credential"),
                first.get("field"),
                f"at {first['institution']}" if first.get("institution") else "",
            ) if part
        )
        sentences.append(f"Education: {label or first.get('notes') or 'recorded'}.")
    elif (profile.acknowledged or {}).get("education"):
        sentences.append("They reported no formal education to record.")
    if profile.skills:
        sentences.append("Skills: " + ", ".join(profile.skills[:12]) + ".")
    if profile.interests:
        sentences.append("Interests: " + ", ".join(profile.interests[:8]) + ".")
    goals = profile.goals or {}
    goal_bits = []
    if goals.get("targetRoles"):
        goal_bits.append("targeting " + ", ".join(goals["targetRoles"][:3]))
    if goals.get("workStyle"):
        goal_bits.append(str(goals["workStyle"]))
    if goals.get("compensation"):
        goal_bits.append(str(goals["compensation"]))
    narrative = str(goals.get("narrative") or "").strip()
    if narrative:
        goal_bits.append(narrative if len(narrative) <= 220 else narrative[:217].rstrip() + "...")
    if goal_bits:
        sentences.append("Next job: " + "; ".join(goal_bits) + ".")
    profile.summary = _clip(" ".join(sentences), 4000)


def _guided_turn(profile: CareerProfile, text: str, missing_before: list[str]) -> str:
    section = _named_section(text) or (missing_before[0] if missing_before else "goals")
    replacing = text.lower().startswith(("actually", "instead", "correction", "replace"))
    if section in {"experience", "education"} and _is_none(text):
        acknowledged = dict(profile.acknowledged or {})
        acknowledged[section] = True
        profile.acknowledged = acknowledged
        if section == "experience":
            profile.experience = []
        else:
            profile.education = []
        captured = f"Noted — no {section} to record."
    elif _too_thin(section, text):
        return f"Say a little more about {section}. {QUESTIONS[section]}"
    else:
        _capture(profile, section, text, replacing)
        if section in missing_sections(profile) and section in missing_before:
            return f"I couldn't file that as {section} yet. {QUESTIONS[section]}"
        captured = _ack(section, profile)
    refresh_summary(profile)
    still = missing_sections(profile)
    if not still:
        return f"{captured} {_review_reply(profile)}"
    if still[0] == section:
        return f"I need a little more on {section}. {QUESTIONS[section]}"
    return f"{captured} {QUESTIONS[still[0]]}"


def _model_turn(
    profile: CareerProfile,
    text: str,
    history: list[tuple[str, str]],
    settings: Settings,
    client: httpx.Client | None,
    target: AiTarget | None = None,
) -> TurnResult:
    messages = [{"role": "system", "content": _system_prompt(profile)}]
    messages.extend({"role": role, "content": content} for role, content in history[-24:])
    messages.append({"role": "user", "content": text})
    if target is not None and target.kind == "opencode":
        result = complete_opencode(messages, target.model_id, target.api_key, client)
    else:
        result = complete_chat(messages, settings, client)
    payload = _parse_payload(result.content)
    if payload is None or not str(payload.get("reply") or "").strip():
        raise ValueError("Model did not return a reply.")
    _merge_model(profile, payload)
    if isinstance(payload.get("summary"), str) and payload["summary"].strip():
        profile.summary = _clip(payload["summary"], 4000)
    else:
        refresh_summary(profile)
    reply = _clip(str(payload["reply"]).strip(), 2000)
    return TurnResult(reply, "model", "Review what the coach captured before you save it.", False)


def _merge_model(profile: CareerProfile, payload: dict) -> None:
    experience = _clean_items(_as_dicts(payload.get("experience")), _clean_experience, 20)
    if experience:
        profile.experience = experience
        _clear_ack(profile, "experience")
    education = _clean_items(_as_dicts(payload.get("education")), _clean_education, 15)
    if education:
        profile.education = education
        _clear_ack(profile, "education")
    skills = _as_terms(payload.get("skills"))
    if skills:
        profile.skills = _clean_terms(skills, 60)
    interests = _as_terms(payload.get("interests"))
    if interests:
        profile.interests = _clean_terms(interests, 40)
    if isinstance(payload.get("goals"), dict):
        current = {**empty_goals(), **(profile.goals or {})}
        incoming = _full_goals(payload["goals"])
        for key, value in incoming.items():
            if value:
                current[key] = value
        profile.goals = current
    acknowledged = payload.get("acknowledged")
    if isinstance(acknowledged, dict):
        current_ack = dict(profile.acknowledged or {})
        for key in ("experience", "education"):
            if acknowledged.get(key) is True and not getattr(profile, key):
                current_ack[key] = True
            elif acknowledged.get(key) is False:
                current_ack.pop(key, None)
        profile.acknowledged = current_ack


def _capture(profile: CareerProfile, section: str, text: str, replacing: bool) -> None:
    if section == "experience":
        item = _parse_experience(text)
        profile.experience = [item] if replacing else [*(profile.experience or []), item][-20:]
        _clear_ack(profile, "experience")
    elif section == "education":
        item = _parse_education(text)
        profile.education = [item] if replacing else [*(profile.education or []), item][-15:]
        _clear_ack(profile, "education")
    elif section == "skills":
        found = _split_list(text)
        profile.skills = found if replacing or not profile.skills else _merge_terms(profile.skills, found)
    elif section == "interests":
        found = _split_list(text)
        profile.interests = found if replacing or not profile.interests else _merge_terms(profile.interests, found)
    else:
        goals = {**empty_goals(), **(profile.goals or {})}
        narrative = text if replacing or not goals["narrative"] else f"{goals['narrative']}\n{text}"
        goals["narrative"] = _clip(narrative, 4000)
        _enrich_goals(goals, text)
        profile.goals = goals


def _parse_experience(text: str) -> dict:
    title, company = "", ""
    match = re.search(
        r"(?:worked as|work as|i was|i am|i'm|i’m) (?:an? )?([A-Za-z][\w/+.&' -]{1,50}?) (?:at|@) ([A-Za-z0-9][\w&.'' -]{1,60})",
        text,
        re.I,
    )
    if not match:
        match = re.search(r"\b([A-Z][\w/+.&' -]{1,40}?) (?:at|@) ([A-Z][\w&.'' -]{1,60})", text)
    if match:
        title = _label(match.group(1))
        company = _label(match.group(2))
    years = re.findall(r"\b(?:19|20)\d{2}\b", text)
    return _clean_experience({
        "title": title,
        "company": company,
        "start": years[0] if years else "",
        "end": years[1] if len(years) > 1 else "",
        "highlights": text,
    })


def _parse_education(text: str) -> dict:
    lower = text.lower()
    credential = next((label for word, label in _CREDENTIALS if word in lower), "")
    institution = ""
    found = re.search(r"(?:at|from) ([A-Z][\w&.'' -]{2,80})", text)
    if found:
        institution = _stop(found.group(1))
    field = ""
    field_match = re.search(r"\bin ([A-Za-z][\w ]{2,40})", text)
    if field_match:
        field = _stop(field_match.group(1))
    years = re.findall(r"\b(?:19|20)\d{2}\b", text)
    return _clean_education({
        "institution": institution,
        "credential": credential,
        "field": field,
        "year": years[-1] if years else "",
        "notes": text,
    })


def _enrich_goals(goals: dict, text: str) -> None:
    lower = text.lower()
    if "hybrid" in lower:
        goals["workStyle"] = "hybrid"
    elif "on-site" in lower or "onsite" in lower or "in office" in lower or "in-office" in lower:
        goals["workStyle"] = "on-site"
    elif "remote" in lower:
        goals["workStyle"] = "remote"
    pay = re.search(r"\$[\d,]+(?:\s?[kK])?(?:\s*[-–]\s*\$?[\d,]+(?:\s?[kK])?)?", text)
    if pay:
        goals["compensation"] = pay.group(0)
    for pattern in _ROLE_PATTERNS:
        match = re.search(pattern, text, re.I)
        if not match:
            continue
        title = _stop(match.group(1))
        title = re.split(r"\b(roles?|positions?|jobs?|hybrid|remote|onsite|on-site|around)\b|\$", title, maxsplit=1, flags=re.I)[0]
        title = title.strip(" .")
        if title and title.lower() not in {item.lower() for item in goals["targetRoles"]}:
            goals["targetRoles"] = [*goals["targetRoles"], title][:12]
        break
    place = re.search(r"(?:based in|located in|open to) ([A-Za-z][\w .,-]{2,40})", text, re.I)
    if place:
        location = _stop(place.group(1))
        if location and location.lower() not in {item.lower() for item in goals["locations"]}:
            goals["locations"] = [*goals["locations"], location][:12]


def _system_prompt(profile: CareerProfile) -> str:
    context = json.dumps(career_context(profile), ensure_ascii=False)
    return (
        "You are the SufferTracker career coach. Interview this person so later coaching can help with their job search. "
        "Learn five areas: experience, education, skills, interests, and goals for their next job.\n"
        "Rules:\n"
        "- Ask one focused question at a time. Keep reply under 90 words.\n"
        "- Be calm and specific. Do not hype, lecture, or invent facts.\n"
        "- Record only what the user said. Leave unknown fields blank.\n"
        "- When a section is good enough, move to the next missing one.\n"
        "- When nothing is missing, summarize in their words and ask them to confirm.\n"
        "- If they correct you, update the profile. Do not argue.\n"
        "- Omit a list or send it empty to leave that section unchanged. When you change a list, send the full replacement.\n"
        "- Set acknowledged.experience or acknowledged.education to true only if they said they have none.\n"
        "Return only JSON with keys reply, experience, education, skills, interests, goals, summary, acknowledged. "
        "Experience items use title, company, start, end, highlights. "
        "Education items use institution, credential, field, year, notes. "
        "Goals uses targetRoles, industries, locations, workStyle, compensation, timeline, narrative, constraints.\n"
        f"Current context JSON:\n{context}"
    )


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


def _ack(section: str, profile: CareerProfile) -> str:
    if section == "experience" and profile.experience:
        item = profile.experience[-1]
        if item.get("title") and item.get("company"):
            return f"I'll remember {item['title']} at {item['company']}."
        return "I'll keep that work history in your context."
    if section == "education":
        return "Education is in."
    if section == "skills" and profile.skills:
        shown = ", ".join(profile.skills[:4])
        return f"Captured {len(profile.skills)} skills: {shown}."
    if section == "interests" and profile.interests:
        return "Noted those interests."
    if section == "goals":
        return "That's a usable picture of the next job."
    return "Got it."


def _review_reply(profile: CareerProfile) -> str:
    brief = profile.summary or "what you shared"
    return f"I have enough to work with. {brief} If that sounds right, say so — or save this context. Correct anything I got wrong."


def _saved_reply() -> str:
    return "Saved. I'll use this context when coaching your search. Update it whenever the target changes."


def _named_section(text: str) -> str | None:
    lowered = text.lower().strip()
    patterns = (
        (r"^(?:actually[, ]+|instead[, ]+)?(?:my |the )?(?:work )?experience\b", "experience"),
        (r"^(?:actually[, ]+)?(?:i |my )?(?:studied|education|degree|school)\b", "education"),
        (r"^(?:actually[, ]+)?(?:my )?skills?(?: are| include|:)\b", "skills"),
        (r"^(?:actually[, ]+)?(?:i am |i'm |im )?interested in\b", "interests"),
        (r"^(?:actually[, ]+)?(?:my )?(?:goal|next job)\b", "goals"),
        (r"^(?:actually[, ]+)?(?:i want to be|i want a |i want an |i'm looking|im looking)\b", "goals"),
    )
    for pattern, section in patterns:
        if re.search(pattern, lowered):
            return section
    return None


def _is_confirm(text: str) -> bool:
    normalized = re.sub(r"[^a-z0-9' ]", "", text.lower()).replace("'", "").strip()
    return len(normalized) <= 40 and normalized in _CONFIRM


def _is_none(text: str) -> bool:
    normalized = re.sub(r"[^a-z0-9' ]", "", text.lower()).replace("'", "").strip()
    if not normalized or len(normalized) > 60:
        return False
    if normalized in _NONE:
        return True
    return normalized.startswith("no ") and any(word in normalized for word in ("experience", "education", "degree", "school"))


def _too_thin(section: str, text: str) -> bool:
    if _named_section(text):
        return False
    if section == "experience":
        return len(text) < 20 and " at " not in text.lower()
    if section == "education":
        return len(text) < 8
    if section == "goals":
        return len(text) < 12
    return False


def _split_list(text: str) -> list[str]:
    raw = text.strip()
    lowered = raw.lower()
    for prefix in (
        "my skills are", "my skills include", "skills:", "i know", "i use",
        "i'm interested in", "im interested in", "i am interested in", "interested in", "interests:", "i like",
    ):
        if lowered.startswith(prefix):
            raw = raw[len(prefix):].strip(" :.-")
            break
    if re.search(r"[,;\n•]", raw) or (raw.lower().count(" and ") >= 1 and len(raw) < 180):
        parts = re.split(r"[,;\n•]|\band\b", raw, flags=re.I)
    else:
        parts = [raw]
    return _clean_terms(parts, 40)


def _clean_terms(values: list, limit: int) -> list[str]:
    items: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = _clip(str(value).strip(" .-•*"), 80)
        key = item.lower()
        if len(item) < 2 or key in seen or key in {"skills", "my skills", "interests", "hmm", "ok", "okay", "yes", "no", "idk", "sure", "thanks", "hello", "hi"}:
            continue
        seen.add(key)
        items.append(item)
        if len(items) >= limit:
            break
    return items


def _merge_terms(current: list[str], found: list[str]) -> list[str]:
    return _clean_terms([*current, *found], 60)


def _as_terms(value: object) -> list[str]:
    if isinstance(value, str):
        return _split_list(value)
    if isinstance(value, list):
        return [str(item) for item in value if isinstance(item, str)]
    return []


def _as_dicts(value: object) -> list[dict]:
    if not isinstance(value, list):
        return []
    items = []
    for item in value:
        if isinstance(item, str) and item.strip():
            items.append({"highlights": item, "notes": item})
        elif isinstance(item, dict):
            items.append(item)
    return items


def _clean_items(values: list[dict], cleaner, limit: int) -> list[dict]:
    cleaned = []
    for item in values:
        if not isinstance(item, dict):
            continue
        parsed = cleaner(item)
        if any(parsed.values()):
            cleaned.append(parsed)
        if len(cleaned) >= limit:
            break
    return cleaned


def _clean_experience(item: dict) -> dict:
    return {
        "title": _clip(_first(item, "title"), 120),
        "company": _clip(_first(item, "company"), 120),
        "start": _clip(_first(item, "start"), 40),
        "end": _clip(_first(item, "end"), 40),
        "highlights": _clip(_first(item, "highlights"), 4000),
    }


def _clean_education(item: dict) -> dict:
    return {
        "institution": _clip(_first(item, "institution"), 160),
        "credential": _clip(_first(item, "credential"), 80),
        "field": _clip(_first(item, "field"), 80),
        "year": _clip(_first(item, "year"), 40),
        "notes": _clip(_first(item, "notes"), 4000),
    }


def _full_goals(raw: dict) -> dict:
    goals = empty_goals()
    roles = raw.get("targetRoles", raw.get("target_roles", []))
    industries = raw.get("industries", [])
    locations = raw.get("locations", [])
    goals["targetRoles"] = _clean_terms(roles if isinstance(roles, list) else _split_list(str(roles or "")), 12)
    goals["industries"] = _clean_terms(industries if isinstance(industries, list) else [], 12)
    goals["locations"] = _clean_terms(locations if isinstance(locations, list) else [], 12)
    for key, aliases in (
        ("workStyle", ("workStyle", "work_style")),
        ("compensation", ("compensation",)),
        ("timeline", ("timeline",)),
        ("narrative", ("narrative",)),
        ("constraints", ("constraints",)),
    ):
        value = _first(raw, *aliases)
        goals[key] = _work_style(value) if key == "workStyle" and value else _clip(value, 4000 if key in {"narrative", "constraints"} else 160)
    return goals


def _work_style(value: str) -> str:
    lower = value.lower()
    if "hybrid" in lower:
        return "hybrid"
    if "on-site" in lower or "onsite" in lower or "office" in lower:
        return "on-site"
    if "remote" in lower:
        return "remote"
    return _clip(value, 40)


def _first(item: dict, *keys: str) -> str:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str):
            return value
    return ""


def _label(value: str) -> str:
    cleaned = _stop(value)
    if cleaned and cleaned == cleaned.lower():
        return cleaned[:1].upper() + cleaned[1:]
    return cleaned


def _stop(value: str) -> str:
    cut = re.split(r"\b(from|where|during|between|with|that|who)\b|[.,]", value, maxsplit=1, flags=re.I)[0]
    return _clip(cut, 80)


def _has_any(profile: CareerProfile) -> bool:
    goals = profile.goals or {}
    return bool(
        profile.experience or profile.education or profile.skills or profile.interests
        or profile.summary or goals.get("narrative") or goals.get("targetRoles") or profile.acknowledged
    )


def _clear_ack(profile: CareerProfile, key: str) -> None:
    acknowledged = dict(profile.acknowledged or {})
    acknowledged.pop(key, None)
    profile.acknowledged = acknowledged


def _clip(value: str, limit: int) -> str:
    return " ".join(value.split())[:limit].strip()

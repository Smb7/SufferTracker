import html
import json
import re
from decimal import Decimal, InvalidOperation

import httpx

from app.schemas import ParsedJobResponse
from app.services.ocr import OcrResult, extract_text
from app.services.url_guard import validate_public_http_url

TITLE_KEYWORDS = [
    "engineer", "developer", "analyst", "manager", "designer", "architect", "scientist", "consultant",
    "specialist", "coordinator", "director", "intern", "administrator", "representative", "accountant",
    "recruiter", "associate", "principal", "staff", "technician", "strategist", "programmer", "devops",
    "product manager", "program manager", "qa ", "sre", "data ", "support",
]
COMPANY_SUFFIXES = [
    "inc", "llc", "ltd", "corp", "corporation", "co", "company", "technologies", "technology", "labs",
    "systems", "software", "solutions", "media", "health", "group", "studio", "ai", "fintech", "ventures",
    "partners", "consulting", "bank", "networks", "digital", "works", "io", "capital", "tech", "cloud", "robotics",
]
COMPANY_BLOCKLIST = {"role", "the role", "this role", "the job", "job", "the company", "company", "us", "the team", "our team", "our", "you", "them", "we", "they", "i", "the position", "position", "join", "team"}
PARENTHETICAL_BLOCKLIST = {"remote", "hybrid", "onsite", "on-site", "on site", "us", "usa", "united states", "canada", "uk", "full-time", "full time", "part-time", "part time", "contract", "temporary", "senior", "junior", "sr", "jr", "mid-level", "lead", "manager", "director", "principal", "staff", "nyc", "sf", "la", "bay area", "austin", "seattle", "redmond", "new york", "global", "worldwide", "us only", "us-only"}
CONNECTOR_WORDS = {"as", "to", "for", "a", "an", "the", "and", "our", "with"}
NOISE_SYMBOLS = set("©®™→←↑↓◈◆□·•")
KNOWN_SKILLS = ["C#", ".NET", "Angular", "TypeScript", "JavaScript", "PostgreSQL", "SQL Server", "Docker", "Kubernetes", "AWS", "Azure", "GCP", "React", "Vue", "Python", "Java", "Go", "Rust", "Terraform", "CI/CD", "REST", "GraphQL"]

HIRING_LINE = re.compile(r"^([A-Z][\w&.,'\- ]{1,48}?)\s+(?:is|are)\s+(?:hiring|looking\s+for|seeking)\b", re.I)
JOIN_LINE = re.compile(r"^(?:join|at)\s+([A-Za-z][\w&.,'\- ]{1,60})", re.I)
ROLE_SENTENCE = re.compile(r"(?:is|are)\s+(?:hiring|looking\s+for|seeking)\s+(?:an?\s+)?([A-Z][A-Za-z0-9&\- ]{2,60}?)(?=\s+(?:to|in|at|on|with|for)\b|\s*[.,:;]|\s*\||\s*$)", re.I)
TITLE_TAG = re.compile(r"(?is)<title\b[^>]*>(.*?)</title>")
OG_TITLE = re.compile(r"""(?is)<meta\b[^>]+(?:property|name)=["']og:title["'][^>]+content=["']([^"']+)["']""")
OG_SITE = re.compile(r"""(?is)<meta\b[^>]+(?:property|name)=["']og:site_name["'][^>]+content=["']([^"']+)["']""")
ABOUT_LINE = re.compile(r"^about\s+(?:the\s+)?([A-Z][\w&.,'\- ]{1,48})", re.I)
REMOTE = re.compile(r"\bremote\b|\bwork from home\b|\bhybrid\b", re.I)
PLACE = re.compile(r"\b([A-Z][a-zA-Z.'-]*(?: [A-Z][a-zA-Z.'-]*){0,3}),\s?(AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY|DC)\b")
SALARY_RANGE = re.compile(r"([$€£])\s?(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s?([kK])?\s?[-–—to]{1,4}\s?([$€£])?\s?(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s?([kK])?\s?(?:/hr|per hour|hourly|/yr|per year|annually|a year)?")
SALARY_SINGLE = re.compile(r"([$€£])\s?(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s?([kK])?\s?(?:/hr|per hour|hourly|/yr|per year|annually|a year)")
HOURLY = re.compile(r"(/hr|per hour|hourly)", re.I)
SALARY_PERIOD = re.compile(r"(per year|annually|a year|/yr)", re.I)
HTML_TAG = re.compile(r"<[^>]+>")
WHITESPACE = re.compile(r"\s+")
BODY = re.compile(r"(?is)<body\b[^>]*>([\s\S]*?)</body>")
NOISY_BLOCK = re.compile(r"(?is)<\b(script|style|noscript|svg|iframe|template)\b[^>]*>[\s\S]*?</\1\s*>")
COMMENT = re.compile(r"<!--[\s\S]*?-->")
BLOCK_BOUNDARY = re.compile(r"(?i)</?(?:p|div|h[1-6]|li|tr|section|article|header|footer|ul|ol|table)\b[^>]*>|<br\s*/?>")
JSON_LD = re.compile(r"""(?is)<script[^>]+type=["']application/ld\+json["'][^>]*>([\s\S]*?)</script>""")
PARENTHETICAL = re.compile(r"\(\s*([A-Z][A-Za-z0-9&.'\- ]{2,30})\s*\)")


def parse_text(text: str) -> ParsedJobResponse:
    if not text or not text.strip():
        raise ValueError("Job text is required.")
    lines = [line.strip() for line in text.replace("\r", "\n").split("\n") if line.strip()]
    title = _find_value(lines, "title", "role", "position") or _extract_title(text, lines)
    company = _find_value(lines, "company", "employer", "organization") or _extract_company(text, lines) or "Unknown company"
    location = _find_value(lines, "location", "based in", "office") or _extract_location(text) or "Location not specified"
    pay = _find_value(lines, "salary", "pay", "compensation") or _extract_pay(text) or "Pay not specified"
    skills = _find_value(lines, "skills", "requirements", "technologies") or _extract_skills(text)
    return ParsedJobResponse(company=company, title=title, description=text.strip(), skills=skills, pay=pay, location=location)


def parse_url(url: str, client: httpx.Client | None = None) -> ParsedJobResponse:
    target = validate_public_http_url(url)
    owns = client is None
    http = client or httpx.Client(timeout=15, follow_redirects=False, headers={"User-Agent": "SufferTracker/1.0 job parser"})
    try:
        response = http.get(target)
        response.raise_for_status()
        parsed = build_parsed_from_html(response.text)
        return parsed.model_copy(update={"source_url": target, "notice": "Review scraped details before saving."})
    finally:
        if owns:
            http.close()


def parse_screenshot(image: bytes, file_name: str, content_type: str, ocr: OcrResult | None = None) -> ParsedJobResponse:
    result = ocr if ocr is not None else extract_text(image, file_name, content_type)
    if not result.text.strip():
        return ParsedJobResponse(company="OCR pending", title="Review uploaded screenshot", description="", skills="", pay="Pay not specified", location="Location not specified", notice=result.notice)
    parsed = parse_text(result.text)
    return parsed.model_copy(update={"notice": result.notice})


def build_parsed_from_html(page: str) -> ParsedJobResponse:
    readable = extract_readable_text(page)
    parsed = parse_text(readable) if readable.strip() else ParsedJobResponse(company="Unknown company", title="Untitled role", description="", skills="", pay="Pay not specified", location="Location not specified")
    structured = try_extract_job_posting(page)
    meta_title, meta_company = _extract_meta(page)
    skills = _first(parsed.skills, _extract_skills(structured["description"]) if structured and structured.get("description") and not parsed.skills else None)
    return parsed.model_copy(update={
        "title": _first(structured.get("title") if structured else None, meta_title, parsed.title),
        "company": _first(structured.get("company") if structured else None, meta_company, parsed.company),
        "pay": (structured.get("pay") if structured and structured.get("pay") else parsed.pay),
        "location": (structured.get("location") if structured and structured.get("location") else parsed.location),
        "description": _first(parsed.description, structured.get("description") if structured else None),
        "skills": skills,
    })


def extract_readable_text(page: str) -> str:
    if not page or not page.strip():
        return ""
    body = BODY.search(page)
    content = body.group(1) if body else page
    content = NOISY_BLOCK.sub(" ", content)
    content = COMMENT.sub(" ", content)
    content = BLOCK_BOUNDARY.sub("\n", content)
    content = HTML_TAG.sub(" ", content)
    decoded = html.unescape(content).replace("\r", "\n")
    lines = [WHITESPACE.sub(" ", line).strip() for line in decoded.split("\n")]
    return "\n".join(line for line in lines if line)


def try_extract_job_posting(page: str) -> dict | None:
    for match in JSON_LD.finditer(page):
        try:
            document = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        posting = _find_job_posting(document)
        if not isinstance(posting, dict):
            continue
        title = posting.get("title") if isinstance(posting.get("title"), str) else None
        company = _read_organization(posting)
        pay = _read_salary(posting)
        location = _read_location(posting)
        description = _strip_html(posting["description"]) if isinstance(posting.get("description"), str) else None
        if title or company or pay or location:
            return {"title": title, "company": company, "pay": pay, "location": location, "description": description}
    return None


def _find_job_posting(element: object) -> dict | None:
    if isinstance(element, dict):
        if _is_job_posting(element.get("@type")):
            return element
        graph = element.get("@graph")
        if isinstance(graph, list):
            for item in graph:
                found = _find_job_posting(item)
                if found:
                    return found
        return None
    if isinstance(element, list):
        for item in element:
            found = _find_job_posting(item)
            if found:
                return found
    return None


def _is_job_posting(value: object) -> bool:
    if isinstance(value, str):
        return value.lower() == "jobposting"
    if isinstance(value, list):
        return any(isinstance(item, str) and item.lower() == "jobposting" for item in value)
    return False


def _read_organization(posting: dict) -> str | None:
    organization = posting.get("hiringOrganization")
    if isinstance(organization, str):
        return organization
    if isinstance(organization, dict) and isinstance(organization.get("name"), str):
        return organization["name"]
    return None


def _read_salary(posting: dict) -> str | None:
    base = posting.get("baseSalary")
    if not isinstance(base, dict):
        return None
    value = base.get("value") if isinstance(base.get("value"), dict) else base
    if not isinstance(value, dict):
        return None
    low = _number(value, "minValue") or _number(value, "value")
    high = _number(value, "maxValue") or low
    if low is None:
        return None
    currency = _currency_symbol(value.get("currency") if isinstance(value.get("currency"), str) else None)
    unit = value.get("unitText") if isinstance(value.get("unitText"), str) else "YEAR"
    suffix = "/hour" if unit.upper() == "HOUR" else " per year"
    if high is not None and high != low:
        return f"{currency}{low:,.0f} - {currency}{high:,.0f}{suffix}"
    return f"{currency}{low:,.0f}{suffix}"


def _number(value: dict, name: str) -> Decimal | None:
    raw = value.get(name)
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return None
    return Decimal(str(raw))


def _currency_symbol(code: str | None) -> str:
    return {"USD": "$", "EUR": "€", "GBP": "£"}.get((code or "").upper(), "$" if not code else f"{code} ")


def _read_location(posting: dict) -> str | None:
    job_location = posting.get("jobLocation")
    address = None
    if isinstance(job_location, list) and job_location and isinstance(job_location[0], dict):
        address = job_location[0].get("address")
    elif isinstance(job_location, dict):
        address = job_location.get("address")
    if not isinstance(address, dict):
        return None
    parts = [address.get("addressLocality"), address.get("addressRegion")]
    joined = ", ".join(part for part in parts if isinstance(part, str) and part.strip())
    return joined or None


def _strip_html(value: str) -> str:
    decoded = html.unescape(NOISY_BLOCK.sub(" ", HTML_TAG.sub(" ", value)))
    return WHITESPACE.sub(" ", decoded).strip()


def _find_value(lines: list[str], *labels: str) -> str | None:
    for line in lines:
        if ":" not in line:
            continue
        label, value = line.split(":", 1)
        if label.strip().lower() in labels:
            return value.strip()
    return None


def _extract_title(text: str, lines: list[str]) -> str:
    sentence = ROLE_SENTENCE.search(text)
    if sentence:
        role = sentence.group(1).strip().rstrip(".,;")
        if 3 <= len(role) <= 80 and role[0].isupper():
            return role
    for line in lines[:8]:
        if len(line) <= 90 and _clean_line(line) and any(keyword in line.lower() for keyword in TITLE_KEYWORDS):
            return _clean_title(line)
    for line in lines[:8]:
        if _clean_line(line):
            return _clean_title(line)
    return "Untitled role"


def _clean_line(line: str) -> bool:
    if len(line) < 2 or len(line) > 100:
        return False
    lowered = line.lower()
    if "suffertracker" in lowered or "src/" in line or "http://" in line or "https://" in line or "www." in line:
        return False
    if any(char in NOISE_SYMBOLS for char in line):
        return False
    if any(char in "[]{}\\_=" for char in line):
        return False
    return True


def _clean_title(line: str) -> str:
    if "|" in line:
        line = line.split("|", 1)[0]
    at_index = line.lower().rfind(" at ")
    if at_index > 0:
        line = line[:at_index]
    dash_index = line.rfind(" - ")
    if dash_index > 0 and any(keyword in line[:dash_index].lower() for keyword in TITLE_KEYWORDS):
        line = line[:dash_index]
    line = line.strip().rstrip("-|")
    return line[:80].strip() if len(line) > 80 else line


def _extract_company(text: str, lines: list[str]) -> str | None:
    for line in lines[:10]:
        for pattern in (HIRING_LINE, JOIN_LINE):
            match = pattern.search(line)
            if match:
                candidate = _normalize_company(_leading_proper_nouns(match.group(1)))
                if candidate:
                    return candidate
        about = ABOUT_LINE.search(line)
        if about:
            candidate = _normalize_company(about.group(1))
            if candidate:
                return candidate
    title_index = _title_line_index(lines)
    for index, raw in enumerate(lines[:10]):
        line = raw.strip().rstrip(".")
        if len(line) < 2 or len(line) > 40 or any(char in line for char in "$·()"):
            continue
        if PLACE.search(line) or REMOTE.search(line) or "|" in line or " at " in line.lower():
            continue
        if line.lower().startswith(("join ", "we ", "our ", "the ")):
            continue
        if any(keyword in line.lower() for keyword in TITLE_KEYWORDS):
            continue
        if any(word in line.lower() for word in ("full-time", "part-time", "contract", "per year")):
            continue
        has_suffix = any(line.lower() == suffix or line.lower().endswith(" " + suffix) for suffix in COMPANY_SUFFIXES)
        near_title = index != title_index and title_index - 1 <= index <= title_index + 2
        if not has_suffix and not near_title:
            continue
        candidate = _normalize_company(line)
        if candidate:
            return candidate
    for line in lines[:6]:
        match = PARENTHETICAL.search(line)
        if not match:
            continue
        candidate = _normalize_company(match.group(1))
        if candidate and candidate.lower() not in PARENTHETICAL_BLOCKLIST:
            return candidate
    return None


def _title_line_index(lines: list[str]) -> int:
    for index, line in enumerate(lines[:4]):
        if len(line) <= 90 and any(keyword in line.lower() for keyword in TITLE_KEYWORDS):
            return index
    return 0


def _normalize_company(candidate: str) -> str | None:
    value = html.unescape(candidate).strip(" .,!-–—|()[]")
    for suffix in ("Careers", "Jobs", "Hiring", "Team", "Careers Site"):
        if value.lower().endswith(" " + suffix.lower()):
            value = value[: -(len(suffix) + 1)].strip()
    if len(value) < 2 or len(value) > 48 or any(char.isdigit() for char in value) or value.lower() in COMPANY_BLOCKLIST:
        return None
    if len(value.split()) > 6:
        return None
    return value


def _extract_meta(page: str) -> tuple[str | None, str | None]:
    og = OG_TITLE.search(page)
    title_tag = TITLE_TAG.search(page)
    raw_title = og.group(1) if og else title_tag.group(1) if title_tag else None
    site = OG_SITE.search(page)
    return _clean_meta_title(raw_title), _normalize_company(site.group(1)) if site else None


def _clean_meta_title(title: str | None) -> str | None:
    if not title or not title.strip():
        return None
    value = WHITESPACE.sub(" ", html.unescape(title).strip())
    if "|" in value:
        value = value.split("|", 1)[0]
    if " - " in value:
        value = value.split(" - ", 1)[0]
    value = value.strip()
    return value if 3 <= len(value) <= 100 else None


def _leading_proper_nouns(phrase: str) -> str:
    kept = []
    for word in phrase.split():
        trimmed = word.rstrip(".!,;:")
        if trimmed.lower() in CONNECTOR_WORDS:
            break
        if kept and not word[:1].isupper():
            break
        if not word[:1].isupper():
            break
        kept.append(word)
    joined = " ".join(kept).strip(" .,!-–—|")
    return joined if 2 <= len(joined) <= 48 else ""


def _extract_location(text: str) -> str | None:
    place = PLACE.search(text)
    if place:
        return f"{place.group(1).strip()}, {place.group(2).upper()}"
    return "Remote" if REMOTE.search(text) else None


def _extract_pay(text: str) -> str | None:
    match = SALARY_RANGE.search(text)
    if match:
        low = _format_amount(match.group(2), match.group(3) or "")
        high_currency = match.group(4) or match.group(1)
        high = _format_amount(match.group(5), match.group(6) or "")
        currency = match.group(1) or match.group(4)
        return f"{currency}{low} - {high_currency}{high}{_suffix(match.group(0))}"
    single = SALARY_SINGLE.search(text)
    if single:
        return f"{single.group(1)}{_format_amount(single.group(2), single.group(3) or '')}{_suffix(single.group(0))}"
    return None


def _format_amount(amount: str, kilo: str) -> str:
    if kilo:
        try:
            return f"{Decimal(amount.replace(',', '')) * 1000:,.0f}"
        except InvalidOperation:
            pass
    return amount.replace(" ", "")


def _suffix(matched: str) -> str:
    if HOURLY.search(matched):
        return "/hour"
    if SALARY_PERIOD.search(matched) or matched[-1:].lower() == "k" or "k" in matched or "K" in matched:
        return " per year"
    return ""


def _extract_skills(text: str) -> str:
    return ", ".join(skill for skill in KNOWN_SKILLS if skill.lower() in text.lower())


def _first(*values: str | None) -> str:
    for value in values:
        if value and value.strip():
            return value
    return ""

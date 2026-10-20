from app.services.ocr import OcrResult
from app.services.parser import build_parsed_from_html, parse_screenshot, parse_text, try_extract_job_posting


def test_parse_text_reads_labeled_fields_and_known_skills() -> None:
    result = parse_text("Senior API Engineer\nCompany: Acme Labs\nLocation: Remote\nSalary: $130k\nSkills: C#, PostgreSQL\nBuild APIs with .NET and Docker.")
    assert result.company == "Acme Labs"
    assert result.title == "Senior API Engineer"
    assert result.location == "Remote"
    assert result.pay == "$130k"
    assert result.skills == "C#, PostgreSQL"


def test_parse_text_uses_safe_defaults() -> None:
    result = parse_text("A thoughtful description for a new role.")
    assert result.title == "A thoughtful description for a new role."
    assert result.company == "Unknown company"
    assert result.pay == "Pay not specified"


def test_parse_text_rejects_empty_input() -> None:
    try:
        parse_text("  ")
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_parse_screenshot_maps_ocr_text() -> None:
    result = parse_screenshot(b"fake", "posting.png", "image/png", OcrResult("Backend Engineer\nCompany: Acme Labs\nLocation: Remote\nSalary: $140k\nSkills: C#, Docker", True, "OCR extracted details."))
    assert result.company == "Acme Labs"
    assert result.title == "Backend Engineer"
    assert result.location == "Remote"
    assert "OCR" in (result.notice or "")


def test_parse_screenshot_pending_when_unconfigured() -> None:
    result = parse_screenshot(b"fake", "posting.png", "image/png", OcrResult("", False, "OCR provider is not configured."))
    assert "OCR" in (result.notice or "")
    assert result.company == "OCR pending"


def test_parse_text_extracts_unlabeled_posting() -> None:
    text = "Senior Backend Engineer\nAcme Robotics is hiring in Austin, TX (Hybrid).\nWe are looking for a senior .NET developer to build APIs.\n$140,000 - $180,000 per year\nRequirements: C#, PostgreSQL, Docker, Azure"
    result = parse_text(text)
    assert result.title == "Senior Backend Engineer"
    assert result.company == "Acme Robotics"
    assert result.location == "Austin, TX"
    assert result.pay == "$140,000 - $180,000 per year"
    assert "C#" in result.skills


def test_parse_text_detects_remote_and_normalizes_pay() -> None:
    result = parse_text("Platform Engineer\nFully remote, work from home anywhere.\n$120k - $150k")
    assert result.location == "Remote"
    assert result.pay == "$120,000 - $150,000 per year"


def test_parse_text_normalizes_pay_formats() -> None:
    assert parse_text("QA Analyst\n$45 - $60 per hour\nRequirements: attention to detail").pay == "$45 - $60/hour"
    assert parse_text("QA Analyst\n$95,000 a year\nRequirements: attention to detail").pay == "$95,000 per year"
    assert parse_text("QA Analyst\n€55/hr\nRequirements: attention to detail").pay == "€55/hour"


def test_parse_text_trims_title_suffixes() -> None:
    assert parse_text("Staff .NET Engineer | Nova Systems\nRemote\n").title == "Staff .NET Engineer"
    assert parse_text("Principal Engineer at Orion Labs\nDenver, CO\n").title == "Principal Engineer"


def test_parse_text_extracts_company_from_join_and_about() -> None:
    assert parse_text("Join Vertex Labs as a data analyst!\nRemote\n").company == "Vertex Labs"
    assert parse_text("Data Analyst\nAbout Copperline: we build mapping software.\n").company == "Copperline"


def test_indeed_style_layout() -> None:
    result = parse_text("Senior Software Engineer\nStripe\nSan Francisco, CA · Remote\n$150,000 - $200,000 a year\nFull-time\nAbout the role: build payments infra.")
    assert result.title == "Senior Software Engineer"
    assert result.company == "Stripe"
    assert result.pay == "$150,000 - $200,000 per year"
    assert result.location == "San Francisco, CA"


def test_looking_for_sentence() -> None:
    result = parse_text("Datadog is looking for a Senior Backend Engineer to join our platform team in New York, NY. Compensation: $180k - $220k.")
    assert result.company == "Datadog"
    assert result.title == "Senior Backend Engineer"
    assert result.pay == "$180,000 - $220,000 per year"


def test_about_the_role_is_not_company() -> None:
    result = parse_text("Product Designer\nFigma\nRemote\nAbout the role: own the design system.\nAbout Figma: we make collaboration tools.")
    assert result.company == "Figma"
    assert result.title == "Product Designer"


def test_json_ld_array_type() -> None:
    page = """<html><body><script type="application/ld+json">
    {"@context":"http://schema.org/","@type":["JobPosting"],
     "title":"Platform Engineer","hiringOrganization":{"@type":"Organization","name":"Vertex Labs"},
     "baseSalary":{"@type":"MonetaryAmount","currency":"USD","value":{"@type":"QuantitativeValue","minValue":160000,"maxValue":190000,"unitText":"YEAR"}}}
    </script></body></html>"""
    result = build_parsed_from_html(page)
    assert result.title == "Platform Engineer"
    assert result.company == "Vertex Labs"
    assert result.pay == "$160,000 - $190,000 per year"


def test_meta_tags_when_json_ld_missing() -> None:
    page = """<html><head><title>Senior Data Analyst - Copperline | LinkedIn</title>
    <meta property="og:site_name" content="Copperline"></head><body><div>job board chrome</div></body></html>"""
    result = build_parsed_from_html(page)
    assert result.title == "Senior Data Analyst"
    assert result.company == "Copperline"


def test_parenthetical_company_and_nearby_lines() -> None:
    starred = parse_text("Software Engineer (Starlink)\nRedmond, WA\n$140,000 - $180,000 a year")
    assert starred.title == "Software Engineer (Starlink)"
    assert starred.company == "Starlink"
    assert starred.location == "Redmond, WA"
    above = parse_text("SpaceX\nSoftware Engineer\nRedmond, WA")
    assert above.company == "SpaceX"
    assert above.title == "Software Engineer"
    careers = parse_text("SpaceX Careers\nSoftware Engineer (Starlink)\nRedmond, WA")
    assert careers.company == "SpaceX"
    remote = parse_text("Data Analyst (Remote)\nAcme Analytics\n$90,000 a year")
    assert remote.company == "Acme Analytics"
    assert remote.location == "Remote"


def test_skips_ocr_noise() -> None:
    text = "[ ] [ ] v © SufferTracker/src/JobTracker\nX © can you only respec once in\nSoftware Engineer (Starlink)\nSpaceX\nRedmond, WA\n$140,000 - $180,000 a year"
    result = parse_text(text)
    assert result.title == "Software Engineer (Starlink)"
    assert result.company == "SpaceX"
    assert result.location == "Redmond, WA"
    assert result.pay == "$140,000 - $180,000 per year"
    noise = parse_text("[ ] [ ] v © SufferTracker/src/JobTracker\nX © respec\n[] → ←")
    assert noise.title == "Untitled role"
    defaults = parse_text("We are looking for someone great.")
    assert defaults.title == "We are looking for someone great."
    assert defaults.company == "Unknown company"
    assert defaults.location == "Location not specified"
    assert defaults.pay == "Pay not specified"


def test_html_strips_noise_and_prefers_json_ld() -> None:
    page = """<html><head><style>.job-card { color: red; }</style><script src="https://cdn.example.com/polyfill.js"></script></head><body>
    <!-- analytics --><script>var trackingId = "abc";</script><h1>Senior Backend Engineer</h1>
    <p>Acme Robotics is hiring in Austin, TX.</p><p>$140,000 - $180,000 per year. Requirements: C#, PostgreSQL, Docker.</p>
    <noscript>Please enable JavaScript.</noscript></body></html>"""
    result = build_parsed_from_html(page)
    assert "trackingId" not in result.description
    assert "polyfill" not in result.description
    assert ".job-card" not in result.description
    assert "enable JavaScript" not in result.description
    assert result.title == "Senior Backend Engineer"
    assert result.company == "Acme Robotics"
    assert result.location == "Austin, TX"
    structured = """<html><body><script type="application/ld+json">{"@type":"JobPosting","title":"Staff Platform Engineer","hiringOrganization":{"name":"Northwind Data"},"baseSalary":{"currency":"USD","value":{"minValue":180000,"maxValue":220000,"unitText":"YEAR"}},"jobLocation":{"address":{"addressLocality":"Seattle","addressRegion":"WA"}},"description":"<p>Build the platform. <b>Kubernetes required.</b></p>"}</script></body></html>"""
    preferred = build_parsed_from_html(structured)
    assert preferred.title == "Staff Platform Engineer"
    assert preferred.company == "Northwind Data"
    assert preferred.pay == "$180,000 - $220,000 per year"
    assert preferred.location == "Seattle, WA"
    assert "Kubernetes" in preferred.skills
    assert try_extract_job_posting("""<script type="application/ld+json">{ not valid json !!! }</script><body>Fallback text only.</body>""") is None

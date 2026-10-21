from app.services.requirements import EMPTY_TEXT, NO_TERMS, extract_requirements


def _keys(values: list[str]) -> set[str]:
    return {item.casefold() for item in values}


def test_requirements_section_is_required_and_preferred_stays_preferred() -> None:
    result = extract_requirements(
        title="Backend Engineer",
        company="Acme",
        description="""
We use Docker in production.

Requirements
- Python
- PostgreSQL
- 3 years of REST API design

Preferred
- Kubernetes
- AWS

About the role
You will partner with the platform team and improve developer experience across services.
""",
    )
    assert result["blockedReason"] is None
    assert _keys(result["required"]) == {"python", "postgresql", "rest api design"}
    assert _keys(result["preferred"]) == {"kubernetes", "aws"}
    assert "docker" in _keys(result["keywords"])
    assert "developer experience" not in _keys(result["keywords"])
    assert "platform team" not in _keys(result["required"])


def test_skills_line_without_a_requirements_section_is_not_blocked() -> None:
    result = extract_requirements(
        title="Designer",
        company="Studio",
        description="Skills: Figma, Adobe Illustrator, and prototyping\n\nWe are hiring a designer to join the studio.",
        skills="Figma, prototyping",
    )
    assert result["blockedReason"] is None
    assert result["required"] == []
    assert result["preferred"] == []
    assert {"figma", "adobe illustrator", "prototyping"} <= _keys(result["keywords"])


def test_empty_and_vague_postings_are_blocked() -> None:
    empty = extract_requirements(title="Nurse", company="Mercy", description="  ", skills="")
    assert empty["blockedReason"] == EMPTY_TEXT
    assert empty["keywords"] == []

    vague = extract_requirements(
        title="Team member",
        description="We are a great place to work. Join our team and grow your career.",
    )
    assert vague["blockedReason"] == NO_TERMS
    assert vague["required"] == []
    assert vague["keywords"] == []


def test_non_tech_qualifications_are_terms_without_the_known_skill_list() -> None:
    result = extract_requirements(
        title="Clinic Manager",
        company="Mercy Health",
        description="""
Qualifications
- Current RN license
- BLS certification
- Experience with clinic scheduling
- Patient intake

Nice to have
- Spanish
- Epic

About the role
You will lead a small team and improve patient flow.
""",
    )
    assert result["blockedReason"] is None
    assert {"rn license", "bls certification", "clinic scheduling", "patient intake"} <= _keys(result["required"])
    assert {"spanish", "epic"} <= _keys(result["preferred"])
    assert "team" not in _keys(result["required"])
    assert "patient flow" not in _keys(result["keywords"])
    assert "python" not in _keys(result["keywords"])


def test_pasted_text_reuses_the_parser_for_a_labeled_skills_line() -> None:
    result = extract_requirements(description="Title: Support analyst\nCompany: Northwind\nSkills: Excel, Salesforce")
    assert result["title"] == "Support analyst"
    assert result["company"] == "Northwind"
    assert result["blockedReason"] is None
    assert {"excel", "salesforce"} <= _keys(result["keywords"])

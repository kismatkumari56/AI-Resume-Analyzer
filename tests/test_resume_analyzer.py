"""Unit tests for PDF extraction, skill detection, and resume scoring.

The tests use small PDFs generated in memory, so they do not depend on any
sample file being committed to the repository. The Flask upload tests use the
in-process test client and never start a real server.

Run with:

    pytest tests/test_resume_analyzer.py
"""

import io

import pytest
from pypdf import PdfWriter
from pypdf.errors import PdfStreamError

from analyzer.pdf_reader import extract_pdf_sections, extract_pdf_text
from analyzer.resume_extractor import UnsupportedFileFormatError, extract_resume_text
from analyzer.resume_scorer import calculate_resume_score
from analyzer.skills_extractor import extract_skills, get_suggestions
from app import app


SAMPLE_RESUME_LINES = [
    "Jane Doe",
    "jane@example.com | +91 98765 43210",
    "PROFESSIONAL SUMMARY",
    "Software engineer who builds reliable web applications.",
    "SKILLS",
    "Python, Flask, SQL, Git",
    "EXPERIENCE",
    "Built REST APIs with Flask and improved response times.",
    "EDUCATION",
    "B.Tech in Computer Science, Example University",
    "PROJECTS",
    "AI Resume Analyzer built with Python and Flask.",
]

COMPLETE_RESUME = (
    "Alex Smith\n"
    "alex.smith@example.com | +1 555-123-4567\n"
    "PROFESSIONAL SUMMARY\n"
    "Experienced software engineer specializing in scalable cloud applications.\n"
    "EDUCATION\n"
    "Bachelor of Science in Computer Science, Example University\n"
    "WORK EXPERIENCE\n"
    "Senior Backend Engineer at TechCorp. Developed microservices with Python, "
    "Flask, and Docker.\n"
    "PROJECTS\n"
    "AI Resume Analyzer - Python, Flask, React, SQL, MongoDB, PostgreSQL, Git, "
    "GitHub, Machine Learning, Deep Learning\n"
    "SKILLS\n"
    "Python, Java, C++, JavaScript, HTML, CSS, SQL, Flask, Django, React, "
    "MongoDB, Git, GitHub\n"
    "Additional details describing architectural patterns, unit testing, "
    "continuous integration, deployment pipelines, team leadership, mentoring "
    "junior developers, and code quality initiatives. Successfully delivered "
    "multiple end-to-end commercial web applications with high availability "
    "and performance."
)


def _escape_pdf_text(text):
    """Escape characters that have special meaning inside a PDF string."""
    return (
        text.replace("\\", r"\\")
        .replace("(", r"\(")
        .replace(")", r"\)")
    )


def build_pdf(pages):
    """Build a minimal valid PDF containing one text block per page."""
    if isinstance(pages, str):
        pages = [pages]

    page_count = len(pages)
    font_number = 3 + page_count * 2
    objects = {}

    kids = " ".join(f"{3 + index * 2} 0 R" for index in range(page_count))
    objects[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objects[2] = (
        f"<< /Type /Pages /Kids [{kids}] /Count {page_count} >>"
    ).encode("ascii")

    for index, lines in enumerate(pages):
        page_number = 3 + index * 2
        content_number = page_number + 1
        if isinstance(lines, str):
            lines = [lines]

        commands = ["BT", "/F1 12 Tf", "50 800 Td", "14 TL"]
        for line in lines:
            commands.append(f"({_escape_pdf_text(line)}) Tj")
            commands.append("T*")
        commands.append("ET")
        stream = "\n".join(commands).encode("latin-1")

        objects[page_number] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] "
            f"/Contents {content_number} 0 R "
            f"/Resources << /Font << /F1 {font_number} 0 R >> >> >>"
        ).encode("ascii")
        objects[content_number] = (
            f"<< /Length {len(stream)} >>\nstream\n".encode("ascii")
            + stream
            + b"\nendstream"
        )

    objects[font_number] = (
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"
    )

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number in range(1, font_number + 1):
        offsets.append(len(pdf))
        pdf += f"{number} 0 obj\n".encode("ascii")
        pdf += objects[number]
        pdf += b"\nendobj\n"

    xref_start = len(pdf)
    pdf += f"xref\n0 {font_number + 1}\n".encode("ascii")
    pdf += b"0000000000 65535 f \n"
    for offset in offsets:
        pdf += f"{offset:010d} 00000 n \n".encode("ascii")
    pdf += (
        f"trailer\n<< /Size {font_number + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_start}\n%%EOF\n"
    ).encode("ascii")
    return bytes(pdf)


@pytest.fixture
def sample_pdf(tmp_path):
    path = tmp_path / "sample_resume.pdf"
    path.write_bytes(build_pdf([SAMPLE_RESUME_LINES]))
    return path


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Flask test client backed by an isolated upload directory."""
    monkeypatch.setitem(app.config, "UPLOAD_FOLDER", str(tmp_path))
    with app.test_client() as test_client:
        yield test_client


# ---------------------------------------------------------------------------
# PDF extraction
# ---------------------------------------------------------------------------

def test_extracts_text_from_sample_pdf(sample_pdf):
    text = extract_pdf_text(str(sample_pdf))

    assert "Jane Doe" in text
    assert "jane@example.com" in text
    assert "Python, Flask, SQL, Git" in text
    assert "Example University" in text


def test_extracts_multiple_pdf_pages_in_order(tmp_path):
    path = tmp_path / "two_pages.pdf"
    path.write_bytes(build_pdf([
        ["FIRST PAGE", "Jane Doe"],
        ["SECOND PAGE", "Python and Flask"],
    ]))

    text = extract_pdf_text(str(path))

    assert "FIRST PAGE" in text
    assert "SECOND PAGE" in text
    assert text.index("FIRST PAGE") < text.index("SECOND PAGE")


def test_extracts_resume_sections_from_pdf(sample_pdf):
    sections = extract_pdf_sections(str(sample_pdf))

    assert "Jane Doe" in sections["header"]
    assert "jane@example.com" in sections["header"]
    assert "Software engineer" in sections["summary"]
    assert "Python" in sections["skills"]
    assert "Built REST APIs" in sections["experience"]
    assert "B.Tech" in sections["education"]
    assert "AI Resume Analyzer" in sections["projects"]


def test_blank_pdf_returns_empty_text(tmp_path):
    path = tmp_path / "blank.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    with open(path, "wb") as file:
        writer.write(file)

    assert extract_pdf_text(str(path)) == ""


def test_corrupt_pdf_raises_a_pdf_error(tmp_path):
    path = tmp_path / "corrupt.pdf"
    path.write_bytes(b"this is not a valid PDF document")

    with pytest.raises(PdfStreamError):
        extract_pdf_text(str(path))


def test_missing_pdf_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        extract_pdf_text(str(tmp_path / "missing.pdf"))


def test_unsupported_resume_format_is_rejected():
    with pytest.raises(UnsupportedFileFormatError):
        extract_resume_text("resume.txt")


# ---------------------------------------------------------------------------
# Skill extraction
# ---------------------------------------------------------------------------

def test_detects_common_technical_skills():
    skills = extract_skills(
        "Skills: Python, Java, JavaScript, SQL, Flask, React, Git and Docker"
    )

    assert {"Python", "Java", "JavaScript", "SQL", "Flask", "React", "Git",
            "Docker"}.issubset(set(skills))


def test_skill_detection_is_case_insensitive_and_deduplicated():
    skills = extract_skills("PYTHON, Python, python3, JavaScript, JS, js")

    assert skills.count("Python") == 1
    assert skills.count("JavaScript") == 1
    assert set(skills) == {"Python", "JavaScript"}


def test_skill_aliases_are_normalized():
    skills = set(extract_skills("JS, Postgres, K8s, sklearn, ReactJS"))

    assert "JavaScript" in skills
    assert "PostgreSQL" in skills
    assert "Kubernetes" in skills
    assert "Scikit-Learn" in skills
    assert "React" in skills


def test_empty_or_missing_resume_has_no_skills():
    assert extract_skills("") == []
    assert extract_skills(None) == []
    assert extract_skills("   \n\t ") == []


def test_skill_names_do_not_match_inside_unrelated_words():
    skills = extract_skills("Pythonic code and NoSQL databases")

    assert "Python" not in skills
    assert "SQL" not in skills


def test_suggestions_cover_missing_core_skills():
    suggestions = get_suggestions([])

    assert any("Python" in item for item in suggestions)
    assert any("SQL" in item for item in suggestions)
    assert any("Git" in item for item in suggestions)
    assert any("Machine Learning" in item for item in suggestions)


def test_complete_skill_list_returns_positive_suggestion():
    suggestions = get_suggestions([
        "Python", "SQL", "Git", "Machine Learning", "Communication",
    ])

    assert len(suggestions) == 1
    assert "Keep your skills updated" in suggestions[0]


# ---------------------------------------------------------------------------
# Resume scoring
# ---------------------------------------------------------------------------

def test_complete_resume_scores_full_marks():
    result = calculate_resume_score(COMPLETE_RESUME)

    assert result["score"] == 100
    assert result["breakdown"] == {
        "Contact Information": 10,
        "Professional Summary": 10,
        "Technical Skills": 20,
        "Education": 15,
        "Experience": 15,
        "Projects": 20,
        "Readability": 10,
    }
    assert result["improvement_areas"] == []


@pytest.mark.parametrize("resume_text", [None, "", "   \n\t  "])
def test_empty_resume_scores_zero(resume_text):
    result = calculate_resume_score(resume_text)

    assert result["score"] == 0
    assert all(points == 0 for points in result["breakdown"].values())


@pytest.mark.parametrize(
    "resume_text",
    [
        COMPLETE_RESUME,
        "Jane Doe\njane@example.com\nEducation: Example College",
        "Python, SQL, Git",
        "Random words without any resume sections",
        "",
    ],
)
def test_breakdown_always_sums_to_total_score(resume_text):
    result = calculate_resume_score(resume_text)

    assert result["score"] == sum(result["breakdown"].values())
    assert 0 <= result["score"] <= 100


@pytest.mark.parametrize(
    "text, expected_contact_score",
    [
        ("jane@example.com", 5),
        ("+1 555-123-4567", 5),
        ("jane@example.com | +1 555-123-4567", 10),
        ("No contact details in this resume", 0),
    ],
)
def test_contact_information_points(text, expected_contact_score):
    result = calculate_resume_score(text)

    assert result["breakdown"]["Contact Information"] == expected_contact_score


def test_technical_skill_score_is_capped_at_twenty():
    many_skills = (
        "Python, Java, C++, C, JavaScript, HTML, CSS, SQL, Flask, Django, "
        "React, MongoDB, Git, GitHub, TensorFlow, Pandas"
    )
    result = calculate_resume_score(many_skills)

    assert result["breakdown"]["Technical Skills"] == 20
    assert len(result["detected_skills"]) >= 10


def test_missing_sections_produce_improvement_areas():
    result = calculate_resume_score(
        "Jane Doe\njane@example.com\nEducation: Example College"
    )
    categories = {area["category"] for area in result["improvement_areas"]}

    assert {"Professional Summary", "Experience", "Projects"}.issubset(categories)
    assert all(area["points_lost"] > 0 for area in result["improvement_areas"])
    assert all(area["suggestion"] for area in result["improvement_areas"])


def test_scoring_is_deterministic():
    first = calculate_resume_score(COMPLETE_RESUME)
    second = calculate_resume_score(COMPLETE_RESUME)

    assert first["score"] == second["score"]
    assert first["breakdown"] == second["breakdown"]


# ---------------------------------------------------------------------------
# Invalid input and Flask integration (no server required)
# ---------------------------------------------------------------------------

def test_analyze_without_a_file_reports_an_error(client):
    response = client.post("/analyze", data={})

    assert response.status_code == 200
    assert "Please upload a resume." in response.get_data(as_text=True)


def test_analyze_rejects_unsupported_file_types(client):
    response = client.post(
        "/analyze",
        data={"resume": (io.BytesIO(b"plain text"), "resume.txt")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert "Only PDF and DOCX files are allowed." in response.get_data(as_text=True)


def test_analyze_rejects_a_corrupt_pdf(client):
    response = client.post(
        "/analyze",
        data={"resume": (io.BytesIO(b"not really a pdf"), "resume.pdf")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert "Unable to analyze this PDF" in response.get_data(as_text=True)


def test_api_reports_missing_file_as_json(client):
    response = client.post("/api/analyze", data={})

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["status"] == "error"
    assert payload["code"] == "MISSING_FILE"


def test_api_analyzes_sample_pdf_without_starting_a_server(client):
    response = client.post(
        "/api/analyze",
        data={
            "resume": (io.BytesIO(build_pdf([SAMPLE_RESUME_LINES])), "resume.pdf")
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "success"
    assert isinstance(payload["score"], int)
    assert 0 <= payload["score"] <= 100
    assert "Python" in payload["skills"]
    assert payload["skill_count"] == len(payload["skills"])


def test_uploaded_pdf_renders_analysis_results(client):
    response = client.post(
        "/analyze",
        data={
            "resume": (io.BytesIO(build_pdf([SAMPLE_RESUME_LINES])), "resume.pdf")
        },
        content_type="multipart/form-data",
    )

    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Your Resume Analysis" in body
    assert "Python" in body


def test_blank_pdf_upload_is_rejected(client):
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    buffer = io.BytesIO()
    writer.write(buffer)

    response = client.post(
        "/analyze",
        data={"resume": (io.BytesIO(buffer.getvalue()), "blank.pdf")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    assert "No readable text found in this PDF." in response.get_data(as_text=True)

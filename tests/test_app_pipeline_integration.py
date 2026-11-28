import io
import os
import unittest
import zipfile
from unittest.mock import patch

from docx import Document

from analyzer.docx_reader import MAX_UNPACKED_SIZE
from analyzer.ocr import OCRError
from app import app


def make_sample_docx_bytes(text="Jane Doe\njane@example.com\nSKILLS\nPython, SQL\n"):
    doc = Document()
    for line in text.splitlines():
        doc.add_paragraph(line)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


class TestAppPipelineIntegration(unittest.TestCase):

    def setUp(self):
        self.client = app.test_client()

    def test_roadmap_incorporates_selected_target_role_and_skill_gap(self):
        """Skill gap & target role must propagate into generated improvement roadmap."""
        resp = self.client.post(
            "/api/analyze",
            data={
                "resume": (io.BytesIO(make_sample_docx_bytes()), "resume.docx"),
                "target_role": "Frontend Developer",
            },
            content_type="multipart/form-data",
            headers={"Accept": "application/json"},
        )
        self.assertEqual(resp.status_code, 200)
        payload = resp.get_json()
        self.assertEqual(payload["status"], "success")
        self.assertEqual(payload["skill_gap"]["target_role"], "Frontend Developer")
        self.assertEqual(payload["roadmap"]["target_role"], "Frontend Developer")

        # Verify skill-gap remediation tasks exist in roadmap
        categories = {t["category"] for t in payload["roadmap"]["all_tasks"]}
        self.assertIn("Skill Development", categories)

    def test_api_analyze_includes_all_pipeline_modules(self):
        """API JSON response should provide complete parity with UI analysis sections."""
        resp = self.client.post(
            "/api/analyze",
            data={"resume": (io.BytesIO(make_sample_docx_bytes()), "resume.docx")},
            content_type="multipart/form-data",
            headers={"Accept": "application/json"},
        )
        self.assertEqual(resp.status_code, 200)
        payload = resp.get_json()
        for key in (
            "section_quality",
            "project_analysis",
            "action_verbs",
            "readability",
            "timeline",
            "certifications",
            "achievements",
            "duplicate_analysis",
            "skill_gap",
            "roadmap",
        ):
            self.assertIn(key, payload)

    @patch("app.match_resume_to_job")
    def test_job_matcher_is_not_called_twice_per_request(self, mock_matcher):
        """match_resume_to_job must execute only once per /analyze invocation."""
        mock_matcher.return_value = {
            "has_job_description": False,
            "matching_skills": [],
            "missing_skills": [],
            "match_percentage": 0,
        }
        resp = self.client.post(
            "/analyze",
            data={"resume": (io.BytesIO(make_sample_docx_bytes()), "resume.docx")},
            content_type="multipart/form-data",
        )
        self.assertEqual(resp.status_code, 200)
        mock_matcher.assert_called_once()

    def test_api_fake_docx_returns_400_json_error(self):
        """Invalid DOCX file sent to /api/analyze must return 400 JSON, not 200 plain text."""
        resp = self.client.post(
            "/api/analyze",
            data={"resume": (io.BytesIO(b"corrupted non-docx bytes"), "fake.docx")},
            content_type="multipart/form-data",
            headers={"Accept": "application/json"},
        )
        self.assertEqual(resp.status_code, 400)
        self.assertTrue(resp.is_json)
        data = resp.get_json()
        self.assertEqual(data["status"], "error")
        self.assertEqual(data["code"], "INVALID_DOCX_FILE")

    @patch("app.extract_resume_text", side_effect=OCRError("Tesseract OCR not available"))
    def test_api_ocr_error_returns_422_json_error(self, _mock_extract):
        """OCRError must route through format_error_response with 422 JSON for API clients."""
        resp = self.client.post(
            "/api/analyze",
            data={"resume": (io.BytesIO(b"%PDF-1.4 dummy"), "scanned.pdf")},
            content_type="multipart/form-data",
            headers={"Accept": "application/json"},
        )
        self.assertEqual(resp.status_code, 422)
        self.assertTrue(resp.is_json)
        data = resp.get_json()
        self.assertEqual(data["code"], "OCR_PROCESSING_ERROR")
        self.assertIn("Tesseract OCR", data["error"])

    def test_roadmap_toggle_rejects_missing_or_invalid_task_id(self):
        """/roadmap/toggle must reject null or nonexistent task_ids instead of polluting session."""
        # Initialize valid session roadmap
        self.client.post(
            "/analyze",
            data={"resume": (io.BytesIO(make_sample_docx_bytes()), "resume.docx")},
            content_type="multipart/form-data",
        )

        resp_missing = self.client.post("/roadmap/toggle", json={"completed": True})
        self.assertEqual(resp_missing.status_code, 400)
        self.assertEqual(resp_missing.get_json()["code"], "INVALID_TASK_ID")

        resp_invalid = self.client.post(
            "/roadmap/toggle", json={"task_id": "non_existent_id", "completed": True}
        )
        self.assertEqual(resp_invalid.status_code, 400)
        self.assertEqual(resp_invalid.get_json()["code"], "INVALID_TASK_ID")

    def test_docx_header_and_table_order_preserved_in_analyze_pipeline(self):
        """Contact info in DOCX header and skills inside a table must be extracted in order."""
        doc = Document()
        doc.sections[0].header.paragraphs[0].text = "alex@example.com | +1 555 234 5678"
        doc.add_paragraph("SKILLS")
        table = doc.add_table(rows=1, cols=2)
        table.rows[0].cells[0].merge(table.rows[0].cells[1]).text = "Python, Docker, Kubernetes"
        doc.add_paragraph("EXPERIENCE")
        doc.add_paragraph("Built cloud APIs.")
        buf = io.BytesIO()
        doc.save(buf)
        buf.seek(0)

        resp = self.client.post(
            "/api/analyze",
            data={"resume": (buf, "resume.docx")},
            content_type="multipart/form-data",
            headers={"Accept": "application/json"},
        )
        self.assertEqual(resp.status_code, 200)
        payload = resp.get_json()
        self.assertEqual(payload["score_breakdown"]["Contact Information"], 10)
        self.assertIn("Docker", payload["skills"])
        self.assertIn("Kubernetes", payload["resume_sections"]["skills"])

    def test_api_docx_zip_bomb_rejected_with_400(self):
        """Oversized unpacked DOCX archive must be rejected before Document parsing."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("word/document.xml", "<w:document/>")
            archive.writestr("big.bin", b"0" * (MAX_UNPACKED_SIZE + 1))
        buf.seek(0)

        resp = self.client.post(
            "/api/analyze",
            data={"resume": (buf, "bomb.docx")},
            content_type="multipart/form-data",
            headers={"Accept": "application/json"},
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json()["code"], "INVALID_DOCX_FILE")

    def test_frontend_templates_and_script_hygiene(self):
        """Verify unified upload script, valid CSS syntax, and non-hardcoded secret key."""
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root_dir, "static", "script.js"), encoding="utf-8") as f:
            script = f.read()
        with open(os.path.join(root_dir, "templates", "result.html"), encoding="utf-8") as f:
            result_html = f.read()

        self.assertNotIn("fileSizeError", script)
        self.assertNotIn("flex-wrap: gap:", result_html)
        self.assertNotEqual(app.secret_key, "resume-ai-roadmap-session-key-2026")


if __name__ == "__main__":
    unittest.main()

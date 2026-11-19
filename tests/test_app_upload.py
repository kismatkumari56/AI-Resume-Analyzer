import io
import os
import unittest

from docx import Document

from app import app

RESUME_LINES = [
    "Jane Doe",
    "jane@example.com | +91 98765 43210 | github.com/jane",
    "SKILLS",
    "Python, Flask, SQL, Git",
    "EXPERIENCE",
    "Built REST APIs with Flask, improving response time by 30%",
    "EDUCATION",
    "B.Tech Computer Science, 2021 - 2025",
]


def make_docx_bytes():
    document = Document()
    for line in RESUME_LINES:
        document.add_paragraph(line)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def make_pdf_bytes():
    """Build a tiny one-page PDF containing the resume lines."""
    commands = ["BT /F1 12 Tf 50 780 Td 16 TL"]
    for line in RESUME_LINES:
        safe = line.replace("(", "").replace(")", "")
        commands.append(f"({safe}) Tj T*")
    commands.append("ET")
    stream = "\n".join(commands)

    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] "
        "/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    pdf = "%PDF-1.4\n"
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf += f"{number} 0 obj\n{body}\nendobj\n"

    xref_start = len(pdf)
    pdf += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n"
    for offset in offsets:
        pdf += f"{offset:010d} 00000 n \n"
    pdf += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_start}\n%%EOF\n"
    )
    return pdf.encode("latin-1")


class UploadTests(unittest.TestCase):

    def setUp(self):
        self.client = app.test_client()
        # Other tests may leave files here, so remember what already exists
        self.files_before = set(os.listdir(app.config["UPLOAD_FOLDER"]))

    def upload(self, content, filename):
        return self.client.post(
            "/analyze",
            data={"resume": (io.BytesIO(content), filename)},
            content_type="multipart/form-data",
        ).get_data(as_text=True)

    def assert_uploads_empty(self):
        """The uploaded file must be deleted after the analysis."""
        files_now = set(os.listdir(app.config["UPLOAD_FOLDER"]))
        self.assertEqual(files_now - self.files_before, set())

    def test_docx_resume_goes_through_the_analysis(self):
        html = self.upload(make_docx_bytes(), "resume.docx")

        self.assertIn("ATS Compatibility Analysis", html)
        self.assertIn("Python", html)
        self.assert_uploads_empty()

    def test_uppercase_extension_is_accepted(self):
        html = self.upload(make_docx_bytes(), "RESUME.DOCX")

        self.assertIn("ATS Compatibility Analysis", html)

    def test_pdf_resume_still_works(self):
        html = self.upload(make_pdf_bytes(), "resume.pdf")

        self.assertIn("ATS Compatibility Analysis", html)
        self.assertIn("Python", html)
        self.assertIn("/download-txt-report", html)
        self.assertIn("Export as TXT", html)
        self.assert_uploads_empty()
        self.assert_uploads_empty()

    def test_pdf_and_docx_find_the_same_skills(self):
        pdf_html = self.upload(make_pdf_bytes(), "resume.pdf")
        docx_html = self.upload(make_docx_bytes(), "resume.docx")

        for skill in ["Python", "Flask", "SQL", "Git"]:
            self.assertIn(skill, pdf_html)
            self.assertIn(skill, docx_html)

    def test_other_file_types_are_rejected(self):
        for name in ["resume.txt", "resume.doc", "resume.exe", "resume"]:
            message = self.upload(b"hello", name)
            self.assertEqual(message, "Only PDF and DOCX files are allowed.")

    def test_fake_docx_is_rejected(self):
        message = self.upload(b"not really a word file", "resume.docx")

        self.assertEqual(message, "This file is not a valid DOCX document.")
        self.assert_uploads_empty()

    def test_fake_pdf_keeps_the_old_error_message(self):
        message = self.upload(b"not really a pdf", "resume.pdf")

        self.assertEqual(
            message, "Unable to analyze this PDF. Please try another PDF."
        )
        self.assert_uploads_empty()

    def test_blank_docx_says_no_readable_text(self):
        buffer = io.BytesIO()
        Document().save(buffer)

        message = self.upload(buffer.getvalue(), "blank.docx")

        self.assertEqual(message, "No readable text found in this DOCX.")

    def test_blank_pdf_says_no_readable_text(self):
        from pypdf import PdfWriter

        writer = PdfWriter()
        writer.add_blank_page(width=72, height=72)
        buffer = io.BytesIO()
        writer.write(buffer)

        message = self.upload(buffer.getvalue(), "blank.pdf")

        self.assertEqual(message, "No readable text found in this PDF.")
        self.assert_uploads_empty()


if __name__ == "__main__":
    unittest.main()

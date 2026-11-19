import unittest
import os
import tempfile
from unittest.mock import MagicMock, patch

from docx import Document
from docx.opc.exceptions import PackageNotFoundError
from pypdf import PdfWriter
from pypdf.errors import PdfStreamError

from analyzer.resume_extractor import (
    UnsupportedFileFormatError,
    extract_docx_text,
    extract_pdf_text,
    extract_resume_text,
)


class ResumeExtractorTests(unittest.TestCase):

    @patch("analyzer.resume_extractor.PdfReader")
    def test_extract_pdf_text_preserves_page_order(self, reader_class):
        first_page = MagicMock()
        first_page.extract_text.return_value = "First page"
        second_page = MagicMock()
        second_page.extract_text.return_value = "Second page"
        reader_class.return_value.pages = [first_page, second_page]

        self.assertEqual(
            extract_pdf_text("resume.pdf"),
            "First page\nSecond page\n",
        )

    @patch("analyzer.resume_extractor.Document")
    def test_extract_docx_text_preserves_paragraph_order(self, document_class):
        document_class.return_value.paragraphs = [
            MagicMock(text="Name"),
            MagicMock(text="Experience"),
        ]

        self.assertEqual(
            extract_docx_text("resume.docx"),
            "Name\nExperience",
        )

    def test_extract_docx_text_includes_table_content(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "resume.docx")
            document = Document()
            document.add_paragraph("Name")
            table = document.add_table(rows=1, cols=2)
            table.cell(0, 0).text = "Python"
            table.cell(0, 1).text = "Flask"
            document.save(path)

            text = extract_docx_text(path)

        self.assertIn("Name", text)
        self.assertIn("Python", text)
        self.assertIn("Flask", text)

    def test_extract_empty_docx_text_returns_empty_string(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "empty.docx")
            Document().save(path)

            self.assertEqual(extract_docx_text(path), "")

    @patch("analyzer.resume_extractor.PdfReader")
    def test_extract_pdf_text_cleans_whitespace_and_keeps_line_breaks(
        self, reader_class
    ):
        page = MagicMock()
        page.extract_text.return_value = (
            "  Jane   Doe \r\n\r\n\r\n SKILLS \x0c Python,\tFlask  "
        )
        reader_class.return_value.pages = [page]

        self.assertEqual(
            extract_pdf_text("resume.pdf"),
            "Jane Doe\n\nSKILLS\nPython, Flask\n",
        )

    @patch("analyzer.resume_extractor.PdfReader")
    def test_extract_pdf_text_normalizes_ligatures(self, reader_class):
        page = MagicMock()
        page.extract_text.return_value = "e\ufb03cient  developer"
        reader_class.return_value.pages = [page]

        self.assertIn("efficient developer", extract_pdf_text("resume.pdf"))

    @patch("analyzer.resume_extractor.PdfReader")
    def test_extract_pdf_text_skips_unreadable_pages(self, reader_class):
        first_page = MagicMock()
        first_page.extract_text.return_value = "First page"
        broken_page = MagicMock()
        broken_page.extract_text.side_effect = ValueError("bad page")
        last_page = MagicMock()
        last_page.extract_text.return_value = "Last page"
        reader_class.return_value.pages = [
            first_page,
            broken_page,
            last_page,
        ]

        self.assertEqual(
            extract_pdf_text("resume.pdf"),
            "First page\nLast page\n",
        )

    @patch("analyzer.resume_extractor.PdfReader")
    def test_extract_pdf_text_skips_none_page_text(self, reader_class):
        first_page = MagicMock()
        first_page.extract_text.return_value = "Page 1"
        none_page = MagicMock()
        none_page.extract_text.return_value = None
        last_page = MagicMock()
        last_page.extract_text.return_value = "Page 2"
        reader_class.return_value.pages = [first_page, none_page, last_page]

        self.assertEqual(
            extract_pdf_text("resume.pdf"),
            "Page 1\nPage 2\n",
        )

    @patch("analyzer.resume_extractor.PdfReader")
    def test_extract_pdf_text_returns_empty_string_without_text(
        self, reader_class
    ):
        page = MagicMock()
        page.extract_text.return_value = "  \n\t  \n"
        reader_class.return_value.pages = [page]

        self.assertEqual(extract_pdf_text("resume.pdf"), "")

    def test_extract_pdf_text_reads_multiple_pages(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "resume.pdf")
            writer = PdfWriter()
            writer.add_blank_page(width=72, height=72)
            writer.add_blank_page(width=72, height=72)
            with open(path, "wb") as file:
                writer.write(file)

            self.assertEqual(extract_pdf_text(path), "")

    def test_corrupted_documents_raise_extraction_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            pdf_path = os.path.join(directory, "broken.pdf")
            docx_path = os.path.join(directory, "broken.docx")
            for path in (pdf_path, docx_path):
                with open(path, "wb") as file:
                    file.write(b"not a valid document")

            with self.assertRaises(PdfStreamError):
                extract_pdf_text(pdf_path)
            with self.assertRaises(PackageNotFoundError):
                extract_docx_text(docx_path)

    @patch("analyzer.resume_extractor.extract_docx_text")
    def test_dispatches_docx_extraction(self, extractor):
        extractor.return_value = "DOCX text"

        self.assertEqual(extract_resume_text("RESUME.DOCX"), "DOCX text")
        extractor.assert_called_once_with("RESUME.DOCX")

    def test_rejects_unsupported_extensions(self):
        with self.assertRaises(UnsupportedFileFormatError):
            extract_resume_text("resume.txt")


if __name__ == "__main__":
    unittest.main()

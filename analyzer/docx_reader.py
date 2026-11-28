"""Extract text from DOCX (Microsoft Word) resumes."""

import zipfile

from docx import Document
from docx.document import Document as DocumentObject
from docx.opc.exceptions import PackageNotFoundError
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table, _Cell
from docx.text.paragraph import Paragraph

# A DOCX is a zip file. Refuse files that would unpack to a huge size
# (a "zip bomb"), even though the upload itself is small.
MAX_UNPACKED_SIZE = 50 * 1024 * 1024  # 50 MB


class DocxReadError(Exception):
    """Raised when a file is not a valid DOCX. The message is safe to show."""


def check_docx_file(filepath):
    """Make sure the file really is a DOCX before opening it."""
    if not zipfile.is_zipfile(filepath):
        raise DocxReadError("This file is not a valid DOCX document.")

    with zipfile.ZipFile(filepath) as archive:
        # Every DOCX has this file; other zip files do not.
        if "word/document.xml" not in archive.namelist():
            raise DocxReadError("This file is not a valid DOCX document.")

        unpacked_size = sum(item.file_size for item in archive.infolist())

        if unpacked_size > MAX_UNPACKED_SIZE:
            raise DocxReadError("This DOCX file is too large to analyze.")


def iter_blocks(parent):
    """Yield the paragraphs and tables of a document or table cell in order.

    python-docx lists paragraphs and tables separately, which loses their
    order. Reading the XML children keeps the order the resume was written in,
    and that order matters for section detection.
    """
    if isinstance(parent, DocumentObject):
        parent_element = parent.element.body
    elif isinstance(parent, _Cell):
        parent_element = parent._tc
    else:
        parent_element = parent._element

    for child in parent_element.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, parent)
        elif isinstance(child, CT_Tbl):
            yield Table(child, parent)


def collect_lines(parent):
    """Return the non-empty text lines of a document, header or table cell."""
    lines = []

    for block in iter_blocks(parent):

        if isinstance(block, Paragraph):
            text = block.text.strip()
            if text:
                lines.append(text)
            continue

        # Merged cells repeat the same cell, so remember what was read.
        seen_cells = set()

        for row in block.rows:
            for cell in row.cells:
                if cell._tc in seen_cells:
                    continue
                seen_cells.add(cell._tc)
                lines.extend(collect_lines(cell))

    return lines


def extract_docx_text(filepath):
    """Extract the text of a DOCX resume as one string."""
    check_docx_file(filepath)

    try:
        document = Document(filepath)
    except (PackageNotFoundError, KeyError, zipfile.BadZipFile):
        raise DocxReadError("This file is not a valid DOCX document.")

    lines = []

    # Contact details are often placed in the page header.
    for section in document.sections:
        if section.header.is_linked_to_previous:
            continue
        for line in collect_lines(section.header):
            if line not in lines:
                lines.append(line)

    lines.extend(collect_lines(document))

    return "\n".join(lines) + "\n" if lines else ""
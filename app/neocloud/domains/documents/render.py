"""DOCX output: a branded renderer for AI-written Markdown, and helpers that fill
the placeholders of TensorBay's standard forms without touching their formatting."""

import io
import re

import docx
from docx.document import Document as DocxDocument
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor
from docx.text.paragraph import Paragraph

PURPLE = RGBColor(0x4B, 0x2E, 0x83)
GREY = RGBColor(0x66, 0x66, 0x66)
FONT = "Calibri"
TENSORBAY_TAGLINE = "GPU Cloud & AI Infrastructure"
FOOTER = "TensorBay Technology, LLC · Confidential · Draft for review"

_BOLD = re.compile(r"(\*\*[^*]+\*\*|(?<![*\w])\*[^*\s][^*]*\*(?![*\w]))")


# --------------------------------------------------------------------------- #
# Markdown -> branded DOCX
# --------------------------------------------------------------------------- #
def _runs(par: Paragraph, text: str, *, size: float | None = None, bold: bool = False) -> None:
    for part in _BOLD.split(text):
        if not part:
            continue
        is_bold = part.startswith("**") and part.endswith("**") and len(part) > 4
        is_italic = not is_bold and part.startswith("*") and part.endswith("*") and len(part) > 2
        run = par.add_run(part[2:-2] if is_bold else part[1:-1] if is_italic else part)
        run.bold = bold or is_bold
        run.italic = is_italic or None
        run.font.name = FONT
        if size:
            run.font.size = Pt(size)


def _shade(cell, hex_fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_fill)
    tc_pr.append(shd)


def _table(doc: DocxDocument, rows: list[list[str]]) -> None:
    width = max(len(r) for r in rows)
    table = doc.add_table(rows=len(rows), cols=width)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, row in enumerate(rows):
        for j in range(width):
            cell = table.cell(i, j)
            par = cell.paragraphs[0]
            _runs(par, row[j] if j < len(row) else "", size=9.5, bold=(i == 0))
            if i == 0:
                _shade(cell, "E9E3F7")
    doc.add_paragraph()


def _footer_and_header(doc: DocxDocument, title: str) -> None:
    section = doc.sections[0]
    head = section.header.paragraphs[0]
    head.text = ""
    r = head.add_run("TensorBay")
    r.bold = True
    r.font.size = Pt(12)
    r.font.color.rgb = PURPLE
    r.font.name = FONT
    r2 = head.add_run(f"   {TENSORBAY_TAGLINE}")
    r2.font.size = Pt(9)
    r2.font.color.rgb = GREY
    r2.font.name = FONT
    foot = section.footer.paragraphs[0]
    foot.text = ""
    foot.alignment = WD_ALIGN_PARAGRAPH.CENTER
    f = foot.add_run(f"{FOOTER} · {title}")
    f.font.size = Pt(8)
    f.font.color.rgb = GREY
    f.font.name = FONT


def markdown_to_docx(markdown: str, title: str) -> bytes:
    """Render simple Markdown (headings, bullets, numbered lists, tables, **bold**)."""
    doc = docx.Document()
    normal = doc.styles["Normal"]
    normal.font.name = FONT
    normal.font.size = Pt(10.5)
    for style in ("Heading 1", "Heading 2", "Heading 3"):
        st = doc.styles[style]
        st.font.name = FONT
        st.font.color.rgb = PURPLE
    _footer_and_header(doc, title)

    lines = markdown.replace("\r\n", "\n").split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        stripped = line.strip()
        if not stripped or re.fullmatch(r"[-*_]{3,}", stripped):
            i += 1
            continue
        if stripped.startswith("```"):  # drop stray code fences the model may add
            i += 1
            continue
        if stripped.startswith("|"):
            rows: list[list[str]] = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                    rows.append(cells)
                i += 1
            if rows:
                _table(doc, rows)
            continue
        m = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if m:
            level = min(len(m.group(1)), 3)
            doc.add_heading(m.group(2).replace("**", ""), level=level if level > 1 or len(doc.paragraphs) else 0)
            i += 1
            continue
        m = re.match(r"^[-*•]\s+(.*)$", stripped)
        if m:
            _runs(doc.add_paragraph(style="List Bullet"), m.group(1))
            i += 1
            continue
        m = re.match(r"^\d+[.)]\s+(.*)$", stripped)
        if m:
            _runs(doc.add_paragraph(style="List Number"), m.group(1))
            i += 1
            continue
        _runs(doc.add_paragraph(), stripped)
        i += 1

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# --------------------------------------------------------------------------- #
# Filling a standard form
# --------------------------------------------------------------------------- #
def replace_in_paragraph(par: Paragraph, old: str, new: str) -> bool:
    """Replace ``old`` with ``new`` keeping the formatting of the run where it starts.

    Works when ``old`` spans several runs. Returns True if anything changed.
    """
    runs = par.runs
    full = "".join(r.text for r in runs)
    start = full.find(old)
    if start < 0:
        return False
    end = start + len(old)
    pos = 0
    first = True
    for r in runs:
        r_start, r_end = pos, pos + len(r.text)
        pos = r_end
        if r_end <= start or r_start >= end:
            continue
        a, b = max(start, r_start) - r_start, min(end, r_end) - r_start
        r.text = r.text[:a] + (new if first else "") + r.text[b:]
        first = False
    return True


def _all_paragraphs(doc: DocxDocument):
    yield from doc.paragraphs
    for table in doc.tables:
        for row in table.rows:
            seen = set()
            for cell in row.cells:
                if id(cell._tc) in seen:
                    continue
                seen.add(id(cell._tc))
                yield from cell.paragraphs
    for section in doc.sections:
        yield from section.header.paragraphs
        yield from section.footer.paragraphs


def replace_everywhere(doc: DocxDocument, pairs: list[tuple[str, str]]) -> int:
    """Apply ordered (old, new) replacements to every paragraph. Returns the hit count."""
    hits = 0
    for par in _all_paragraphs(doc):
        for old, new in pairs:
            while old in par.text and replace_in_paragraph(par, old, new):
                hits += 1
                if new and old in new:
                    break
    return hits


def set_cell_text(cell, text: str) -> None:
    """Replace a table cell's text, keeping the first run's formatting."""
    par = cell.paragraphs[0]
    if par.runs:
        par.runs[0].text = text
        for r in par.runs[1:]:
            r.text = ""
    else:
        par.add_run(text)
    for extra in cell.paragraphs[1:]:
        extra._element.getparent().remove(extra._element)


def table_by_header(doc: DocxDocument, first_header: str, second_header: str) -> object | None:
    for t in doc.tables:
        if len(t.rows) and len(t.columns) >= 2 and t.rows[0].cells[0].text.strip() == first_header \
                and t.rows[0].cells[1].text.strip() == second_header:
            return t
    return None


def row_by_label(table, label: str):
    for row in table.rows:
        if row.cells[0].text.strip().lower().startswith(label.lower()):
            return row
    return None


def docx_bytes(doc: DocxDocument) -> bytes:
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()

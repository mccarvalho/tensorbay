"""DOCX output: a branded renderer for AI-written Markdown, and helpers that fill
the placeholders of TensorBay's standard forms without touching their formatting."""

import copy
import difflib
import io
import re

import docx
import docx.text.run
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
def _bold_slice(run, a: int, b: int) -> None:
    """Make characters [a, b) of a run bold by splitting it into up to three runs (same formatting otherwise)."""
    text = run.text
    if a >= b or a < 0 or b > len(text):
        return
    pieces = [(text[:a], False), (text[a:b], True), (text[b:], False)]
    pieces = [p for p in pieces if p[0]]
    base = copy.deepcopy(run._r)
    anchor = run._r
    for i, (chunk, bold) in enumerate(pieces):
        if i == 0:
            target = run
        else:
            el = copy.deepcopy(base)
            anchor.addnext(el)
            anchor = el
            target = docx.text.run.Run(el, run._parent)
        target.text = chunk
        if bold:
            target.bold = True


def replace_in_paragraph(par: Paragraph, old: str, new: str, *, bold: bool = True) -> bool:
    """Replace ``old`` with ``new`` keeping the formatting of the run where it starts.

    Works when ``old`` spans several runs. The words of ``new`` that are not in ``old`` are set in bold: it is the data TensorBay filled into the form.
    Returns True if anything changed.
    """
    runs = par.runs
    full = "".join(r.text for r in runs)
    start = full.find(old)
    if start < 0:
        return False
    end = start + len(old)
    pos = 0
    first = True
    first_run = None
    first_at = 0
    for r in runs:
        r_start, r_end = pos, pos + len(r.text)
        pos = r_end
        if r_end <= start or r_start >= end:
            continue
        a, b = max(start, r_start) - r_start, min(end, r_end) - r_start
        if first:
            first_run, first_at = r, a
        r.text = r.text[:a] + (new if first else "") + r.text[b:]
        first = False
    if bold and first_run is not None and new:
        spans, at = [], first_at
        for chunk, is_new in diff_segments(old, new):
            if is_new:
                spans.append((at, at + len(chunk)))
            at += len(chunk)
        for a, b in reversed(spans):  # last first: earlier offsets stay valid after a split
            _bold_slice(first_run, a, b)
    return True


def _tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"\s+|\S+?(?=[.,;:)]*(?:\s|$))|[.,;:)]+", text) if t]


def diff_segments(old: str, new: str) -> list[tuple[str, bool]]:
    """Split ``new`` into (text, is_new) parts: is_new marks what differs from ``old`` (word level)."""
    a, b = _tokens(old), _tokens(new)
    segs: list[list] = []
    for op, _i1, _i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        chunk = "".join(b[j1:j2])
        if chunk:
            segs.append([chunk, op in ("replace", "insert")])
    for i in range(1, len(segs) - 1):  # a space between two filled values belongs to them
        if not segs[i][1] and not segs[i][0].strip() and segs[i - 1][1] and segs[i + 1][1]:
            segs[i][1] = True
    merged: list[list] = []
    for text, flag in segs:
        if merged and merged[-1][1] == flag:
            merged[-1][0] += text
        else:
            merged.append([text, flag])
    return [(t, f) for t, f in merged]


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


def set_cell_text(cell, text: str, *, bold: bool = False, old: str | None = None) -> None:
    """Replace a table cell's text, keeping the first run's formatting.

    ``bold`` sets the whole new text in bold; ``old`` (the previous text) sets in bold only what changed.
    """
    par = cell.paragraphs[0]
    if par.runs:
        base = copy.deepcopy(par.runs[0]._r)
        par.runs[0].text = text
        for r in par.runs[1:]:
            r.text = ""
    else:
        par.add_run(text)
        base = None
    for extra in cell.paragraphs[1:]:
        extra._element.getparent().remove(extra._element)
    if not (bold or old is not None) or not text:
        return
    segs = [(text, True)] if old is None else diff_segments(old, text)
    if not any(flag for _t, flag in segs):
        return
    first = par.runs[0]
    anchor = first._r
    for i, (chunk, flag) in enumerate(segs):
        if i == 0:
            target = first
        else:
            el = copy.deepcopy(base if base is not None else first._r)
            anchor.addnext(el)
            anchor = el
            target = docx.text.run.Run(el, first._parent)
        target.text = chunk
        if flag:
            target.bold = True


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


def fill_blank(paragraphs, label: str, value: str) -> bool:
    """In the paragraph that has ``label`` followed by a run of underscores, put ``value``
    where the blank is ("Legal entity: ______" -> "Legal entity: Acme"). First match only."""
    import re

    for par in paragraphs:
        m = re.search(re.escape(label) + r"\s*_{2,}", par.text)
        if m:
            return replace_in_paragraph(par, m.group(0), f"{label} {value}")
    return False


def cell_paragraphs(cell):
    return list(cell.paragraphs)

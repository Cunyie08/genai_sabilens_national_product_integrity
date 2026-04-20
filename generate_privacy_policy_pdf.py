"""
Converts PRIVACY_POLICY.md to a structured PDF using ReportLab.
All **bold** markers are converted to proper bold; no asterisks appear in output.
"""

import re
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY

BASE_DIR   = Path(__file__).parent
INPUT_MD   = BASE_DIR / "PRIVACY_POLICY.md"
OUTPUT_PDF = BASE_DIR / "SabiLens_Privacy_Policy.pdf"

BRAND_GREEN  = colors.HexColor("#1A7A4A")
BRAND_DARK   = colors.HexColor("#0D1F13")
TABLE_HEADER = colors.HexColor("#1A7A4A")
TABLE_ALT    = colors.HexColor("#F2FAF5")
RULE_COLOR   = colors.HexColor("#B2D8C0")
TEXT_GREY    = colors.HexColor("#4A4A4A")


def md_inline(text):
    """Convert inline markdown to ReportLab XML. Strips all bare asterisks."""
    text = re.sub(r"&(?!amp;|lt;|gt;|quot;|apos;|#)", "&amp;", text)
    text = re.sub(r"\*{3}(.+?)\*{3}", r"<b><i>\1</i></b>", text)
    text = re.sub(r"\*{2}(.+?)\*{2}", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", text)
    text = re.sub(r"`(.+?)`", r"<font name='Courier'>\1</font>", text)
    # Strip any remaining bare asterisks
    text = re.sub(r"\*+", "", text)
    return text


def build_styles():
    s = {}
    s["doc_title"] = ParagraphStyle("doc_title",
        fontName="Helvetica-Bold", fontSize=22, textColor=BRAND_GREEN,
        spaceAfter=6, alignment=TA_CENTER)
    s["doc_subtitle"] = ParagraphStyle("doc_subtitle",
        fontName="Helvetica", fontSize=10, textColor=TEXT_GREY,
        spaceAfter=4, alignment=TA_CENTER)
    s["h1"] = ParagraphStyle("h1",
        fontName="Helvetica-Bold", fontSize=13, textColor=BRAND_GREEN,
        spaceBefore=18, spaceAfter=6, leading=16)
    s["h2"] = ParagraphStyle("h2",
        fontName="Helvetica-Bold", fontSize=11, textColor=BRAND_DARK,
        spaceBefore=12, spaceAfter=4, leading=14)
    s["h3"] = ParagraphStyle("h3",
        fontName="Helvetica-BoldOblique", fontSize=10, textColor=TEXT_GREY,
        spaceBefore=8, spaceAfter=3, leading=13)
    s["body"] = ParagraphStyle("body",
        fontName="Helvetica", fontSize=9.5, textColor=BRAND_DARK,
        spaceBefore=3, spaceAfter=3, leading=14, alignment=TA_JUSTIFY)
    s["bullet"] = ParagraphStyle("bullet",
        fontName="Helvetica", fontSize=9.5, textColor=BRAND_DARK,
        spaceBefore=2, spaceAfter=2, leading=13,
        leftIndent=16, firstLineIndent=0, alignment=TA_LEFT)
    s["numbered"] = ParagraphStyle("numbered",
        fontName="Helvetica", fontSize=9.5, textColor=BRAND_DARK,
        spaceBefore=2, spaceAfter=2, leading=13,
        leftIndent=20, firstLineIndent=-12, alignment=TA_LEFT)
    s["italic_note"] = ParagraphStyle("italic_note",
        fontName="Helvetica-Oblique", fontSize=8.5, textColor=TEXT_GREY,
        spaceBefore=12, spaceAfter=4, leading=13, alignment=TA_JUSTIFY)
    s["table_header"] = ParagraphStyle("table_header",
        fontName="Helvetica-Bold", fontSize=9, textColor=colors.white, leading=12)
    s["table_cell"] = ParagraphStyle("table_cell",
        fontName="Helvetica", fontSize=9, textColor=BRAND_DARK, leading=12)
    return s


def build_table(header_row, data_rows, styles, col_widths=None):
    pw = A4[0] - 4 * cm
    if col_widths is None:
        n = len(header_row)
        col_widths = [pw / n] * n

    def ph(t): return Paragraph(md_inline(t), styles["table_header"])
    def pc(t): return Paragraph(md_inline(t), styles["table_cell"])

    rows = [[ph(h) for h in header_row]]
    for row in data_rows:
        rows.append([pc(c) for c in row])

    tbl = Table(rows, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0),  TABLE_HEADER),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.white, TABLE_ALT]),
        ("GRID",          (0, 0), (-1, -1), 0.4, RULE_COLOR),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
    ]))
    return tbl


def on_page(canvas, doc):
    canvas.saveState()
    w, h = A4
    canvas.setFillColor(BRAND_GREEN)
    canvas.rect(0, h - 1.2 * cm, w, 1.2 * cm, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 9)
    canvas.drawString(2 * cm, h - 0.82 * cm, "SabiLens")
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(w - 2 * cm, h - 0.82 * cm, "Privacy Policy - April 2026")
    canvas.setStrokeColor(RULE_COLOR)
    canvas.setLineWidth(0.5)
    canvas.line(2 * cm, 1.4 * cm, w - 2 * cm, 1.4 * cm)
    canvas.setFillColor(TEXT_GREY)
    canvas.setFont("Helvetica", 7.5)
    canvas.drawCentredString(w / 2, 0.8 * cm, f"Page {doc.page}")
    canvas.drawString(2 * cm, 0.8 * cm,
        "NCC Digital Innovation Park, Kobape, Abeokuta, Ogun State, Nigeria")
    canvas.drawRightString(w - 2 * cm, 0.8 * cm, "privacy@sabilens.com")
    canvas.restoreState()


def convert():
    styles = build_styles()
    story  = []
    lines  = INPUT_MD.read_text(encoding="utf-8").splitlines()

    # Cover block
    story.append(Spacer(1, 1.5 * cm))
    story.append(Paragraph("SabiLens", styles["doc_title"]))
    story.append(Paragraph("Privacy Policy", styles["doc_title"]))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(
        "Effective Date: April 7, 2026 &nbsp;|&nbsp; Last Updated: April 7, 2026",
        styles["doc_subtitle"]))
    story.append(Paragraph(
        "Grounded in the Nigeria Data Protection Act 2023 (NDPA) &amp; "
        "Nigeria Data Protection Regulation 2019 (NDPR)",
        styles["doc_subtitle"]))
    story.append(Spacer(1, 0.4 * cm))
    story.append(HRFlowable(width="100%", thickness=1.5, color=BRAND_GREEN, spaceAfter=12))

    table_buf  = []
    bullet_buf = []

    def flush_bullets():
        for b in bullet_buf:
            story.append(Paragraph(
                "<bullet>&bull;</bullet>" + md_inline(b), styles["bullet"]))
        bullet_buf.clear()

    def flush_table():
        if len(table_buf) < 2:
            table_buf.clear()
            return
        header = [c.strip() for c in table_buf[0].strip("|").split("|")]
        data = []
        for row in table_buf[2:]:  # skip separator row (---|---)
            data.append([c.strip() for c in row.strip("|").split("|")])
        n = len(header)
        pw = A4[0] - 4 * cm
        col_widths = [pw * 0.38, pw * 0.62] if n == 2 else [pw / n] * n
        story.append(build_table(header, data, styles, col_widths))
        story.append(Spacer(1, 6))
        table_buf.clear()

    i = 0
    while i < len(lines):
        ln = lines[i]

        # Table rows
        if ln.startswith("|"):
            flush_bullets()
            table_buf.append(ln)
            i += 1
            continue
        elif table_buf:
            flush_table()

        # Blank line
        if ln.strip() == "":
            flush_bullets()
            story.append(Spacer(1, 4))
            i += 1
            continue

        # Skip MD title (already rendered in cover block)
        if re.match(r"^# SabiLens Privacy Policy", ln):
            i += 1
            continue

        # Skip effective/last-updated lines (already in cover block)
        if re.match(r"^\*\*(?:Effective Date|Last Updated):", ln):
            i += 1
            continue

        # Horizontal rule
        if re.match(r"^-{3,}$", ln.strip()):
            flush_bullets()
            story.append(HRFlowable(width="100%", thickness=0.5, color=RULE_COLOR,
                spaceBefore=4, spaceAfter=4))
            i += 1
            continue

        # H1
        if ln.startswith("# "):
            flush_bullets()
            story.append(HRFlowable(width="100%", thickness=0.5, color=RULE_COLOR,
                spaceBefore=6, spaceAfter=2))
            story.append(Paragraph(md_inline(ln[2:]), styles["h1"]))
            i += 1
            continue

        # H2
        if ln.startswith("## "):
            flush_bullets()
            story.append(Paragraph(md_inline(ln[3:]), styles["h2"]))
            i += 1
            continue

        # H3
        if ln.startswith("### "):
            flush_bullets()
            story.append(Paragraph(md_inline(ln[4:]), styles["h3"]))
            i += 1
            continue

        # Numbered list
        m = re.match(r"^(\d+)\.\s+(.*)", ln)
        if m:
            flush_bullets()
            story.append(Paragraph(
                f"<b>{m.group(1)}.</b>&nbsp;&nbsp;{md_inline(m.group(2))}",
                styles["numbered"]))
            i += 1
            continue

        # Bullet list
        if re.match(r"^[-*]\s", ln):
            bullet_buf.append(ln[2:])
            i += 1
            continue

        # Italic closing paragraph (*...*)
        if re.match(r"^\*[^*]", ln) and ln.rstrip().endswith("*"):
            flush_bullets()
            inner = ln.strip().lstrip("*").rstrip("*")
            story.append(Paragraph(md_inline(inner), styles["italic_note"]))
            i += 1
            continue

        # Body paragraph
        flush_bullets()
        story.append(Paragraph(md_inline(ln), styles["body"]))
        i += 1

    flush_bullets()
    if table_buf:
        flush_table()

    doc = SimpleDocTemplate(
        str(OUTPUT_PDF),
        pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=2.2 * cm, bottomMargin=2 * cm,
        title="SabiLens Privacy Policy",
        author="SabiLens",
        subject="Privacy Policy - NDPA 2023 & NDPR 2019",
    )
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    print(f"PDF generated: {OUTPUT_PDF}")


if __name__ == "__main__":
    convert()

import re

try:
    from fpdf import FPDF
    _FPDF_OK = True
except ImportError:
    _FPDF_OK = False


def to_markdown_bytes(report: str) -> bytes:
    return report.encode("utf-8")


def to_pdf_bytes(report: str, query: str) -> bytes:
    if not _FPDF_OK:
        raise RuntimeError("fpdf2 not installed. Run: pip install fpdf2")

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.set_left_margin(20)
    pdf.set_right_margin(20)
    pdf.set_top_margin(20)
    pdf.add_page()

    # After add_page(), pdf.epw = effective page width (page - margins)
    W = pdf.epw

    for line in report.split("\n"):
        raw = line.rstrip()

        if raw.startswith("## "):
            pdf.ln(4)
            pdf.set_font("Helvetica", "B", 15)
            pdf.multi_cell(W, 8, _safe(raw[3:]))

        elif raw.startswith("### "):
            pdf.ln(3)
            pdf.set_font("Helvetica", "B", 12)
            pdf.multi_cell(W, 7, _safe(raw[4:]))
            pdf.ln(1)

        elif raw.startswith("#### "):
            pdf.ln(2)
            pdf.set_font("Helvetica", "B", 11)
            pdf.multi_cell(W, 6, _safe(raw[5:]))

        elif re.match(r"^[-*] ", raw):
            pdf.set_font("Helvetica", "", 10)
            pdf.multi_cell(W, 5.5, _safe("    * " + raw[2:]))

        elif re.match(r"^\d+\. ", raw):
            pdf.set_font("Helvetica", "", 10)
            pdf.multi_cell(W, 5.5, _safe("    " + raw))

        elif raw in ("", "---"):
            pdf.ln(3)

        else:
            pdf.set_font("Helvetica", "", 10)
            pdf.multi_cell(W, 5.5, _safe(raw))

    return bytes(pdf.output())


def _safe(text: str) -> str:
    """Strip markdown syntax and encode to latin-1 for fpdf2 core fonts."""
    text = re.sub(r"\*\*\*(.*?)\*\*\*", r"\1", text)
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"\*(.*?)\*", r"\1", text)
    text = re.sub(r"`(.*?)`", r"\1", text)
    text = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1 (\2)", text)
    text = re.sub(r"\[(.*?)\]", r"\1", text)
    return text.encode("latin-1", errors="replace").decode("latin-1")


def safe_filename(query: str) -> str:
    stem = re.sub(r"[^\w\s-]", "", query.lower()).strip()
    stem = re.sub(r"[\s]+", "_", stem)
    return stem[:50] or "report"

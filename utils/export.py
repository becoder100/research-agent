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
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_margins(left=20, top=20, right=20)
    pdf.add_page()

    W = pdf.epw  # effective page width: 210 - 20 - 20 = 170 mm

    def _write(text: str, style: str = "", size: int = 10,
               h: float = 5.5, gap: float = 0) -> None:
        """Render one text block, always resetting cursor to the left margin."""
        if gap:
            pdf.ln(gap)
        pdf.set_font("Helvetica", style, size)
        pdf.set_x(pdf.l_margin)
        # new_x/new_y are explicit so fpdf2 version differences don't matter
        pdf.multi_cell(W, h, text, new_x="LMARGIN", new_y="NEXT")

    # ── Title block ────────────────────────────────────────────────────────
    _write(_safe(f"Research Report"), style="B", size=18, h=10)
    _write(_safe(query), style="I", size=11, h=6)
    pdf.set_draw_color(56, 189, 248)   # #38bdf8
    pdf.set_x(pdf.l_margin)
    pdf.line(pdf.l_margin, pdf.get_y() + 2, pdf.l_margin + W, pdf.get_y() + 2)
    pdf.ln(7)

    # ── Body ───────────────────────────────────────────────────────────────
    for line in report.split("\n"):
        raw = line.rstrip()

        if not raw or raw == "---":
            pdf.ln(3)

        elif raw.startswith("###### "):
            _write(_safe(raw[7:]), style="B", size=10, h=5.5, gap=2)

        elif raw.startswith("##### "):
            _write(_safe(raw[6:]), style="B", size=10, h=5.5, gap=2)

        elif raw.startswith("#### "):
            _write(_safe(raw[5:]), style="BI", size=11, h=6, gap=2)

        elif raw.startswith("### "):
            _write(_safe(raw[4:]), style="B", size=12, h=6.5, gap=3)

        elif raw.startswith("## "):
            _write(_safe(raw[3:]), style="B", size=14, h=7.5, gap=5)

        elif raw.startswith("# "):
            _write(_safe(raw[2:]), style="B", size=16, h=8.5, gap=5)

        elif re.match(r"^[-*] ", raw):
            _write(_safe("  * " + raw[2:]), size=10, h=5.5)

        elif re.match(r"^\d+\. ", raw):
            _write(_safe("  " + raw), size=10, h=5.5)

        else:
            _write(_safe(raw), size=10, h=5.5)

    return bytes(pdf.output())


def _safe(text: str) -> str:
    """Strip markdown, drop URLs, remove control chars, encode to latin-1."""
    # Remove control characters (null bytes and other non-printable chars
    # can silently stop fpdf2 from rendering the rest of the page)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    # Strip bold / italic markers (handles ***, **, *)
    text = re.sub(r"\*+([^*\n]*)\*+", r"\1", text)

    # Strip inline code
    text = re.sub(r"`+([^`\n]*)`+", r"\1", text)

    # [link text](url) → keep only the link text (URLs break word-wrap)
    text = re.sub(r"\[([^\]\n]*)\]\([^\)\n]*\)", r"\1", text)

    # Bare [text] reference links
    text = re.sub(r"\[([^\]\n]*)\]", r"\1", text)

    # Encode to latin-1 for fpdf2 core fonts (unsupported chars → ?)
    return text.encode("latin-1", errors="replace").decode("latin-1")


def safe_filename(query: str) -> str:
    stem = re.sub(r"[^\w\s-]", "", query.lower()).strip()
    stem = re.sub(r"[\s]+", "_", stem)
    return stem[:50] or "report"

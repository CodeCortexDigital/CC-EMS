"""Fonts for server-made PDFs (invoices, fee receipts, result cards, finance reports).

The built-in PDF fonts (Helvetica) have no Japanese characters, so Japanese names and wording printed as empty boxes. These PDFs now use
Noto Sans JP (SIL Open Font License, see backend/assets/fonts/OFL.txt): regular and bold, trimmed to Latin, kana and the JIS X 0208 kanji
(`scripts/build_jp_font.py`). The font is embedded in each PDF, so it prints the same everywhere. If the font files are missing the PDFs
fall back to Helvetica, as before.
"""
from __future__ import annotations

from pathlib import Path

FONT_DIR = Path(__file__).resolve().parents[2] / 'assets' / 'fonts'
REGULAR, BOLD = 'NotoSansJP', 'NotoSansJP-Bold'
_ready: bool | None = None


def available() -> bool:
    """Register the fonts once; False when the files are not there (then Helvetica is used)."""
    global _ready
    if _ready is None:
        try:
            from reportlab.pdfbase import pdfmetrics  # imported here so a server without ReportLab still starts
            from reportlab.pdfbase.ttfonts import TTFont

            pdfmetrics.registerFont(TTFont(REGULAR, str(FONT_DIR / 'NotoSansJP-Regular.ttf')))
            pdfmetrics.registerFont(TTFont(BOLD, str(FONT_DIR / 'NotoSansJP-Bold.ttf')))
            pdfmetrics.registerFontFamily(REGULAR, normal=REGULAR, bold=BOLD, italic=REGULAR, boldItalic=BOLD)
            _ready = True
        except Exception:  # missing or unreadable file: keep the old look rather than failing the document
            _ready = False
    return _ready


def base() -> str:
    return REGULAR if available() else 'Helvetica'


def bold() -> str:
    return BOLD if available() else 'Helvetica-Bold'


def stylesheet():
    """ReportLab's sample styles, set to the Japanese-capable font (headings bold, everything else regular)."""
    from reportlab.lib.styles import getSampleStyleSheet

    styles = getSampleStyleSheet()
    if available():
        for style in styles.byName.values():
            name = getattr(style, 'fontName', '') or ''
            style.fontName = BOLD if 'Bold' in name else REGULAR
    return styles

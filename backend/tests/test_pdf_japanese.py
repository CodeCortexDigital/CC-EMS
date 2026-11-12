"""Server-made PDFs show Japanese (the built-in Helvetica has no Japanese characters)."""
from io import BytesIO
from types import SimpleNamespace

import pytest

from services.pdf import fonts
from services.pdf.pdf_generator import PDFGenerator


def test_the_font_has_every_school_character():
    assert fonts.available() is True
    from reportlab.pdfbase import pdfmetrics

    cmap = pdfmetrics.getFont(fonts.REGULAR).face.charToGlyph
    for ch in '若葉学園みどり市立 山田太郎ヤマダ給食費¥0123456789ABCabc年組':
        assert ord(ch) in cmap, ch
    bold = pdfmetrics.getFont(fonts.BOLD).face.charToGlyph
    assert ord('若') in bold and ord('Z') in bold


def test_styles_use_the_japanese_font():
    styles = fonts.stylesheet()
    assert styles['Normal'].fontName == fonts.REGULAR
    assert styles['Title'].fontName == fonts.BOLD


def _receipt(name='山田 太郎'):
    school = SimpleNamespace(settings_json={}, currency='JPY', name='若葉学園')
    invoice = SimpleNamespace(
        invoice_number='INV-001', opening_balance=0, fee_structure=SimpleNamespace(fee_name='給食費 (4月)'), amount=4800,
        late_fee_amount=0, discount_amount=0, total_amount=4800, paid_amount=0, balance_due=4800, status='pending',
        student=SimpleNamespace(tenant=school))
    student = SimpleNamespace(full_name=name, student_id='WKG-0001', current_class=SimpleNamespace(name='6年1組'))
    return invoice, student


def test_a_fee_receipt_with_japanese_names_embeds_the_japanese_font(db):
    invoice, student = _receipt()
    data = PDFGenerator().generate_fee_receipt(invoice, student, []).getvalue()
    assert data.startswith(b'%PDF')
    assert b'NotoSansJP' in data


def test_without_the_font_files_the_pdf_still_builds_in_helvetica(db, monkeypatch):
    monkeypatch.setattr(fonts, '_ready', False)
    invoice, student = _receipt(name='Amy Alder')
    data = PDFGenerator().generate_fee_receipt(invoice, student, []).getvalue()
    assert data.startswith(b'%PDF') and b'NotoSansJP' not in data

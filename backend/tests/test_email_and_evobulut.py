"""Günlük e-posta özeti ve EvoBulut fatura eşleştirmesi."""

from datetime import date, timedelta
from unittest.mock import patch

import pytest

from app.database import SessionLocal
from app.models import Invoice, InvoiceStatus, Product, StockItem, StockItemStatus


@pytest.fixture
def sent_emails(monkeypatch):
    """Resend'e giden istekleri yakalar; gerçek e-posta gönderilmez."""
    monkeypatch.setattr("app.config.get_settings.__wrapped__", None, raising=False)
    captured = []

    class FakeResponse:
        status_code = 200
        text = "ok"

    def fake_post(url, headers=None, json=None, timeout=None):
        captured.append(json)
        return FakeResponse()

    from app.services import email as email_service

    monkeypatch.setattr(email_service.settings, "resend_api_key", "re_test")
    monkeypatch.setattr(email_service.settings, "smtp_from", "bildirim@7medikal.com")
    monkeypatch.setattr(email_service.requests, "post", fake_post)
    return captured


def _digest():
    from app.services.daily_digest import send_daily_digest

    return send_daily_digest()


def test_digest_not_sent_when_nothing_to_report(client, admin, sent_emails):
    result = _digest()
    assert result["sent"] is False
    assert sent_emails == []


def test_digest_includes_overdue_upcoming_and_expiring(client, admin, sent_emails):
    today = date.today()
    db = SessionLocal()
    db.add(Invoice(invoice_number="GECMIS", due_date=today - timedelta(days=5), amount=1000.0,
                   counterparty="ACME", file_path="", source_filename="a.pdf"))
    db.add(Invoice(invoice_number="YAKIN", due_date=today + timedelta(days=2), amount=500.0,
                   counterparty="BETA", file_path="", source_filename="b.pdf"))
    p = Product(name="Stent", reference_no="R1")
    db.add(p)
    db.flush()
    db.add(StockItem(product_id=p.id, lot_no="LOT9", skt=today + timedelta(days=10),
                     status=StockItemStatus.IN_STOCK))
    db.commit()
    db.close()

    result = _digest()
    assert result["sent"] is True
    body = sent_emails[0]["text"]
    assert "GECMIS" in body and "YAKIN" in body and "LOT9" in body


def test_digest_excludes_paid_invoices_and_used_stock(client, admin, sent_emails):
    today = date.today()
    db = SessionLocal()
    db.add(Invoice(invoice_number="ODENDI", due_date=today - timedelta(days=5), amount=1.0,
                   status=InvoiceStatus.PAID, file_path="", source_filename="a.pdf"))
    db.add(Invoice(invoice_number="ACIK", due_date=today - timedelta(days=5), amount=1.0,
                   file_path="", source_filename="b.pdf"))
    p = Product(name="P", reference_no="R")
    db.add(p)
    db.flush()
    db.add(StockItem(product_id=p.id, lot_no="KULLANILDI", skt=today + timedelta(days=5),
                     status=StockItemStatus.USED))
    db.commit()
    db.close()

    _digest()
    body = sent_emails[0]["text"]
    assert "ACIK" in body
    assert "ODENDI" not in body
    assert "KULLANILDI" not in body


def test_digest_skips_users_who_opted_out(client, admin, sent_emails):
    db = SessionLocal()
    db.add(Invoice(invoice_number="X", due_date=date.today() - timedelta(days=1), amount=1.0,
                   file_path="", source_filename="a.pdf"))
    db.commit()
    db.close()

    client.patch("/auth/me/email-preference", json={"email_notifications_enabled": False}, headers=admin)
    assert _digest()["sent"] is False
    assert sent_emails == []


def test_recipients_use_bcc_so_addresses_stay_private(client, admin, sent_emails):
    db = SessionLocal()
    db.add(Invoice(invoice_number="X", due_date=date.today() - timedelta(days=1), amount=1.0,
                   file_path="", source_filename="a.pdf"))
    db.commit()
    db.close()

    _digest()
    payload = sent_emails[0]
    assert payload["to"] == ["bildirim@7medikal.com"]
    assert "admin@test.com" in payload["bcc"]


EVOBULUT_ROW = {
    "G.a_id": "1351",
    "G.a_tur": "31",
    "G.a_tarih": "24.07.2026 00:00:00",
    "G.a_vtarih": "24.10.2026 00:00:00",
    "CARI_ADI": "MEDİCANA ZİNCİRLİKUYU ",
    "G.a_tutar": "260700",
    "TBL_DOV.a_adi": "TL",
    "G.a_sbelge_seri_no": "MEA2026000000007",
    "Kalan": "0",
}


def test_evobulut_sync_maps_fields_and_marks_paid(client, admin):
    from app.services import evobulut_sync

    with patch.object(evobulut_sync, "fetch_all_sales_invoices", return_value=[EVOBULUT_ROW]), \
         patch.object(evobulut_sync, "fetch_invoice_pdf_url", return_value="https://x/y"), \
         patch.object(evobulut_sync, "download_pdf_bytes", return_value=b"%PDF-1.4 test"):
        result = evobulut_sync.sync_invoices_from_evobulut()

    assert result["created"] == 1
    inv = client.get("/invoices", headers=admin).json()[0]
    assert inv["invoice_number"] == "MEA2026000000007"
    assert inv["invoice_date"] == "2026-07-24"
    assert inv["due_date"] == "2026-10-24"
    assert inv["amount"] == 260700
    assert inv["currency"] == "TRY"
    assert inv["counterparty"] == "MEDİCANA ZİNCİRLİKUYU"
    assert inv["status"] == "paid"  # Kalan == 0


def test_evobulut_sync_is_idempotent(client, admin):
    from app.services import evobulut_sync

    with patch.object(evobulut_sync, "fetch_all_sales_invoices", return_value=[EVOBULUT_ROW]), \
         patch.object(evobulut_sync, "fetch_invoice_pdf_url", return_value=None):
        first = evobulut_sync.sync_invoices_from_evobulut()
        second = evobulut_sync.sync_invoices_from_evobulut()

    assert first["created"] == 1
    assert second["created"] == 0 and second["skipped"] == 1
    assert len(client.get("/invoices", headers=admin).json()) == 1


def test_evobulut_unsent_invoice_number_becomes_null(client, admin):
    from app.services import evobulut_sync

    row = {**EVOBULUT_ROW, "G.a_sbelge_seri_no": "GÖNDERİLMEDİ", "Kalan": "260700"}
    with patch.object(evobulut_sync, "fetch_all_sales_invoices", return_value=[row]), \
         patch.object(evobulut_sync, "fetch_invoice_pdf_url", return_value=None):
        evobulut_sync.sync_invoices_from_evobulut()

    inv = client.get("/invoices", headers=admin).json()[0]
    assert inv["invoice_number"] is None
    assert inv["status"] != "paid"

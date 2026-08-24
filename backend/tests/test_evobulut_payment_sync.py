"""EvoBulut'ta tahsil edilen faturaların uygulamaya yansıması.

Senkronizasyon yalnızca YENİ fatura oluşturuyordu; bir fatura bir kez
aktarıldıktan sonra bir daha güncellenmiyordu. Sonucu: EvoBulut'ta ödenen
fatura uygulamada sonsuza kadar "ödenmemiş" görünüyor, vade uyarıları da
gitmeye devam ediyordu.
"""

from datetime import date

import pytest

from app.database import SessionLocal
from app.models import Invoice, InvoiceStatus
from app.services import evobulut_sync


def _item(evobulut_id="1001", kalan="0", tutar="1000", no="MDE2026000000223", **extra):
    item = {
        "G.a_id": evobulut_id,
        "G.a_tutar": tutar,
        "G.a_tarih": "01.08.2026 00:00:00",
        "G.a_vtarih": "31.08.2026 00:00:00",
        "G.a_sbelge_seri_no": no,
        "CARI_ADI": "MEDİPOL MEGA",
        "TBL_DOV.a_adi": "TL",
        "Kalan": kalan,
    }
    item.update(extra)
    return item


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


def _sync(monkeypatch, items):
    monkeypatch.setattr(evobulut_sync, "fetch_all_sales_invoices", lambda **_: items)
    # PDF indirme ağa çıkar; ödeme durumu testinin konusu değil.
    monkeypatch.setattr(evobulut_sync, "_download_pdf", lambda *a, **k: None)
    return evobulut_sync.sync_invoices_from_evobulut()


def test_payment_recorded_later_marks_the_invoice_paid(client, admin, db, monkeypatch):
    """Asıl hata: fatura önce ödenmemiş gelir, sonra EvoBulut'ta tahsil edilir."""
    _sync(monkeypatch, [_item(kalan="1000")])
    invoice = db.query(Invoice).filter(Invoice.evobulut_id == "1001").first()
    assert invoice.status != InvoiceStatus.PAID

    result = _sync(monkeypatch, [_item(kalan="0")])

    db.expire_all()
    invoice = db.query(Invoice).filter(Invoice.evobulut_id == "1001").first()
    assert invoice.status == InvoiceStatus.PAID
    assert result["updated"] == 1
    assert result["created"] == 0


def test_a_manual_paid_mark_is_not_reverted(client, admin, db, monkeypatch):
    """Kullanıcı parayı aldığında elle işaretleyebiliyor; EvoBulut'a işlenmesi
    gün alabilir ve saatlik senkronizasyon bunu geri almamalı."""
    _sync(monkeypatch, [_item(kalan="1000")])
    invoice = db.query(Invoice).filter(Invoice.evobulut_id == "1001").first()
    invoice.status = InvoiceStatus.PAID
    db.commit()

    _sync(monkeypatch, [_item(kalan="1000")])

    db.expire_all()
    invoice = db.query(Invoice).filter(Invoice.evobulut_id == "1001").first()
    assert invoice.status == InvoiceStatus.PAID


def test_invoice_number_arrives_on_a_later_sync(client, admin, db, monkeypatch):
    """E-fatura gönderilene kadar EvoBulut 'GÖNDERİLMEDİ' döndürüyor."""
    _sync(monkeypatch, [_item(no="GÖNDERİLMEDİ")])
    invoice = db.query(Invoice).filter(Invoice.evobulut_id == "1001").first()
    assert invoice.invoice_number is None

    _sync(monkeypatch, [_item(no="MDE2026000000999")])

    db.expire_all()
    invoice = db.query(Invoice).filter(Invoice.evobulut_id == "1001").first()
    assert invoice.invoice_number == "MDE2026000000999"


def test_manual_corrections_are_not_overwritten(client, admin, db, monkeypatch):
    """Dolu alanlara dokunulmaz - yönetici elle düzeltmiş olabilir."""
    _sync(monkeypatch, [_item()])
    invoice = db.query(Invoice).filter(Invoice.evobulut_id == "1001").first()
    invoice.counterparty = "Elle düzeltilmiş firma"
    invoice.due_date = date(2026, 9, 15)
    db.commit()

    _sync(monkeypatch, [_item()])

    db.expire_all()
    invoice = db.query(Invoice).filter(Invoice.evobulut_id == "1001").first()
    assert invoice.counterparty == "Elle düzeltilmiş firma"
    assert invoice.due_date == date(2026, 9, 15)


def test_unchanged_invoice_counts_as_skipped(client, admin, db, monkeypatch):
    _sync(monkeypatch, [_item()])
    result = _sync(monkeypatch, [_item()])

    assert result["updated"] == 0
    assert result["skipped"] == 1


def test_paid_invoice_leaves_the_due_filters(client, admin, db, monkeypatch):
    """Kullanıcının gördüğü sonuç: tahsil edilen fatura vade sekmelerinden
    düşmeli, 'Ödendi' sekmesinde görünmeli."""
    _sync(monkeypatch, [_item(kalan="1000", **{"G.a_vtarih": "01.01.2026 00:00:00"})])
    overdue = client.get("/invoices", params={"overdue_only": True}, headers=admin).json()
    assert len(overdue) == 1

    _sync(monkeypatch, [_item(kalan="0", **{"G.a_vtarih": "01.01.2026 00:00:00"})])

    overdue = client.get("/invoices", params={"overdue_only": True}, headers=admin).json()
    assert overdue == []
    everything = client.get("/invoices", headers=admin).json()
    assert [i["status"] for i in everything] == ["paid"]

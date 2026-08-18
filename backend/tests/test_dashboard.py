"""Yönetici panosu özeti.

Panonun asıl riski yanlış rakam göstermesi: yanlış bir sayı, hiç sayı
göstermemekten kötüdür çünkü yöneticinin kararına girer. Testler bu yüzden
toplama kurallarına odaklanıyor.
"""

from datetime import date, datetime, timedelta

import pytest

from app.database import SessionLocal
from app.models import (
    CheckIn,
    Hospital,
    Invoice,
    InvoiceStatus,
    Product,
    SalesTarget,
    StockItem,
    StockItemStatus,
    User,
)


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


def _summary(client, admin):
    r = client.get("/dashboard/summary", headers=admin)
    assert r.status_code == 200, r.text
    return r.json()


def _invoice(db, **kwargs):
    defaults = dict(file_path="/x.pdf", source_filename="x.pdf", status=InvoiceStatus.PARSED)
    inv = Invoice(**{**defaults, **kwargs})
    db.add(inv)
    db.commit()
    return inv


def test_currencies_are_never_summed_together(client, admin, db):
    """TRY + USD toplamak anlamsız bir rakam üretir; kırılım ayrı olmalı."""
    today = date.today()
    _invoice(db, amount=1000, currency="TRY", invoice_date=today)
    _invoice(db, amount=500, currency="TRY", invoice_date=today)
    _invoice(db, amount=200, currency="USD", invoice_date=today)

    rows = _summary(client, admin)["faturalar"]["bu_ay_kesilen"]

    by_currency = {r["para_birimi"]: r for r in rows}
    assert by_currency["TRY"]["tutar"] == 1500
    assert by_currency["TRY"]["adet"] == 2
    assert by_currency["USD"]["tutar"] == 200


def test_paid_invoices_are_excluded_from_due_figures(client, admin, db):
    """Ödenmiş fatura artık bir alacak değil; vade rakamlarını şişirmemeli."""
    today = date.today()
    _invoice(db, amount=100, due_date=today - timedelta(days=5))
    _invoice(db, amount=999, due_date=today - timedelta(days=5), status=InvoiceStatus.PAID)

    overdue = _summary(client, admin)["faturalar"]["vadesi_gecen"]

    assert len(overdue) == 1
    assert overdue[0]["tutar"] == 100


def test_upcoming_windows_are_nested_not_exclusive(client, admin, db):
    """7 gün içindeki bir fatura 30 gün penceresinde de sayılmalı."""
    _invoice(db, amount=300, due_date=date.today() + timedelta(days=3))

    faturalar = _summary(client, admin)["faturalar"]

    assert faturalar["yaklasan_7_gun"][0]["tutar"] == 300
    assert faturalar["yaklasan_30_gun"][0]["tutar"] == 300


def test_invoices_without_an_amount_do_not_break_totals(client, admin, db):
    """Okunamamış faturalarda tutar boş kalabiliyor."""
    _invoice(db, amount=None, due_date=date.today() - timedelta(days=1), status=InvoiceStatus.NEEDS_REVIEW)

    faturalar = _summary(client, admin)["faturalar"]

    assert faturalar["vadesi_gecen"] == []
    assert faturalar["kontrol_gerekli"] == 1


def test_stock_counts_quantity_not_rows(client, admin, db):
    """Bir satır birden fazla adet taşıyabiliyor; satır saymak yanıltır."""
    hospital = Hospital(name="Test Hastanesi")
    product = Product(name="Test Ürün", reference_no="R1")
    db.add_all([hospital, product])
    db.commit()

    db.add_all([
        StockItem(product_id=product.id, lot_no="L1", quantity=5,
                  status=StockItemStatus.AT_HOSPITAL, hospital_id=hospital.id),
        StockItem(product_id=product.id, lot_no="L2", quantity=3,
                  status=StockItemStatus.AT_HOSPITAL, hospital_id=hospital.id),
    ])
    db.commit()

    stok = _summary(client, admin)["stok"]

    assert stok["hastanelerde_toplam"] == 8
    assert stok["hastane_dagilimi"][0] == {"hastane": "Test Hastanesi", "adet": 8}


def test_used_items_are_left_out_of_expiry_warnings(client, admin, db):
    """Kullanılmış ürünün son kullanma tarihi kimseyi ilgilendirmez."""
    product = Product(name="Test Ürün", reference_no="R1")
    db.add(product)
    db.commit()

    soon = date.today() + timedelta(days=10)
    db.add_all([
        StockItem(product_id=product.id, lot_no="SAHADA", quantity=1,
                  skt=soon, status=StockItemStatus.IN_STOCK),
        StockItem(product_id=product.id, lot_no="KULLANILDI", quantity=1,
                  skt=soon, status=StockItemStatus.USED),
    ])
    db.commit()

    expiring = _summary(client, admin)["stok"]["skt_yaklasan"]

    assert [e["lot_no"] for e in expiring] == ["SAHADA"]
    assert expiring[0]["kalan_gun"] == 10


def test_field_activity_covers_the_last_seven_days(client, admin, db):
    hospital = Hospital(name="H1")
    db.add(hospital)
    db.commit()
    employee = db.query(User).filter(User.email == "admin@test.com").first()

    db.add_all([
        CheckIn(user_id=employee.id, hospital_id=hospital.id, photo_path="a.jpg",
                checked_in_at=datetime.utcnow()),
        # Sekiz gün önce - pencerenin dışında.
        CheckIn(user_id=employee.id, hospital_id=hospital.id, photo_path="b.jpg",
                checked_in_at=datetime.utcnow() - timedelta(days=8)),
    ])
    db.commit()

    saha = _summary(client, admin)["saha"]

    assert saha["son_7_gun_checkin"] == 1
    assert saha["ziyaret_edilen_hastane"] == 1
    assert saha["calisan_dagilimi"][0]["adet"] == 1


def test_only_active_targets_are_shown_lowest_progress_first(client, admin, db):
    today = date.today()
    admin_user = db.query(User).filter(User.email == "admin@test.com").first()

    db.add_all([
        SalesTarget(title="Suren", target_quantity=10, manual_progress=2,
                    period_start=today - timedelta(days=5), period_end=today + timedelta(days=5),
                    created_by_user_id=admin_user.id),
        SalesTarget(title="Iyi giden", target_quantity=10, manual_progress=9,
                    period_start=today - timedelta(days=5), period_end=today + timedelta(days=5),
                    created_by_user_id=admin_user.id),
        SalesTarget(title="Gecmis", target_quantity=10, manual_progress=0,
                    period_start=today - timedelta(days=60), period_end=today - timedelta(days=30),
                    created_by_user_id=admin_user.id),
    ])
    db.commit()

    hedefler = _summary(client, admin)["hedefler"]

    assert [h["baslik"] for h in hedefler] == ["Suren", "Iyi giden"]
    assert hedefler[0]["yuzde"] == 20
    assert hedefler[0]["calisan"] == "Tüm ekip"


def test_progress_above_target_is_capped_at_100_percent(client, admin, db):
    """İlerleme çubuğu taşmasın; rakam ayrıca ham haliyle de dönüyor."""
    today = date.today()
    admin_user = db.query(User).filter(User.email == "admin@test.com").first()
    db.add(SalesTarget(title="Asildi", target_quantity=5, manual_progress=12,
                       period_start=today, period_end=today + timedelta(days=1),
                       created_by_user_id=admin_user.id))
    db.commit()

    hedef = _summary(client, admin)["hedefler"][0]

    assert hedef["yuzde"] == 100
    assert hedef["ilerleme"] == 12


def test_dashboard_is_admin_only(client, employee):
    assert client.get("/dashboard/summary", headers=employee).status_code == 403


def test_empty_system_returns_zeros_not_errors(client, admin):
    """Yeni kurulumda pano boş açılmalı, patlamamalı."""
    summary = _summary(client, admin)

    assert summary["faturalar"]["bu_ay_kesilen"] == []
    assert summary["stok"]["depoda"] == 0
    assert summary["saha"]["son_7_gun_checkin"] == 0
    assert summary["hedefler"] == []

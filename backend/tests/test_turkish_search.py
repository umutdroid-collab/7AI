"""Türkçe karakterli arama.

SQLite'ın lower()'ı yalnızca ASCII küçültüyor; SQLAlchemy `ilike` bunu
kullandığı için "düz" araması yalnızca Title-Case yazılmış kayıtları,
"DÜZ" araması yalnızca BÜYÜK yazılmışları buluyordu. Saha ekibi için bu
"arama çalışmıyor" demekti.
"""

import pytest

from app.database import SessionLocal, turkish_fold
from app.models import Hospital, Invoice, InvoiceStatus, Product, StockItem, StockItemStatus


@pytest.fixture
def products(client, admin):
    db = SessionLocal()
    db.add_all([
        Product(name="Gelweave Düz Vasküler Protez", reference_no="732518"),
        Product(name="GELWEAVE BİFURKE VASKÜLER", reference_no="732519"),
        Product(name="Efferon LPS", reference_no="900100"),
    ])
    db.commit()
    db.close()


def _names(client, admin, q):
    r = client.get("/products", params={"q": q}, headers=admin)
    assert r.status_code == 200
    return {p["name"] for p in r.json()}


def test_lowercase_query_finds_uppercase_records(client, admin, products):
    """Asıl hata buydu: 'düz' yazınca BÜYÜK harfli kayıtlar gelmiyordu."""
    assert _names(client, admin, "vasküler") == {
        "Gelweave Düz Vasküler Protez",
        "GELWEAVE BİFURKE VASKÜLER",
    }


def test_uppercase_query_finds_lowercase_records(client, admin, products):
    assert _names(client, admin, "VASKÜLER") == {
        "Gelweave Düz Vasküler Protez",
        "GELWEAVE BİFURKE VASKÜLER",
    }


def test_query_without_turkish_characters_still_matches(client, admin, products):
    """Telefondan çoğu kişi 'duz vaskuler' diye yazıyor."""
    assert "Gelweave Düz Vasküler Protez" in _names(client, admin, "duz")
    assert len(_names(client, admin, "vaskuler")) == 2


def test_dotted_capital_i_matches_dotless_query(client, admin, products):
    """'BİFURKE' ile 'bifurke' eşleşmeli - Python'un kendi lower()'ı burada
    araya birleşen bir nokta karakteri koyup eşleşmeyi bozuyor."""
    assert _names(client, admin, "bifurke") == {"GELWEAVE BİFURKE VASKÜLER"}


def test_ascii_search_is_unaffected(client, admin, products):
    assert _names(client, admin, "efferon") == {"Efferon LPS"}
    assert _names(client, admin, "732518") == {"Gelweave Düz Vasküler Protez"}


def test_unrelated_query_still_returns_nothing(client, admin, products):
    """Katlama eşleşmeyi genişletiyor; her şeyi eşleştirmemeli."""
    assert _names(client, admin, "kalp kapağı") == set()


def test_stock_search_shares_the_fix(client, admin, products):
    db = SessionLocal()
    hospital = Hospital(name="ACIBADEM ATAKENT")
    db.add(hospital)
    product = db.query(Product).filter(Product.reference_no == "732518").first()
    db.commit()
    db.add(StockItem(product_id=product.id, lot_no="26097014-7684", quantity=1,
                     status=StockItemStatus.AT_HOSPITAL, hospital_id=hospital.id))
    db.commit()
    db.close()

    r = client.get("/stock", params={"q": "vaskuler"}, headers=admin)
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_invoice_search_shares_the_fix(client, admin):
    db = SessionLocal()
    db.add(Invoice(file_path="/x.pdf", source_filename="x.pdf", status=InvoiceStatus.PARSED,
                   invoice_number="MDE1", counterparty="MEDİPOL MEGA"))
    db.commit()
    db.close()

    r = client.get("/invoices", params={"q": "medipol"}, headers=admin)
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_fold_helper_handles_the_turkish_letter_pairs():
    assert turkish_fold("İIıiŞşĞğÜüÖöÇç") == "iiiissggu" + "uoocc"
    assert turkish_fold(None) is None

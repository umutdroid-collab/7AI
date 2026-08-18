"""Asistanın şirket verisi soruları.

En kritik test grubu ilki: yönlendirmenin klinik soruları KAÇIRMAMASI.
Bir iş sorusunun anlaşılmaması can sıkar; bir klinik sorunun iş yoluna
kaçması uygulamanın asıl özelliğini bozar.
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
from app.services import business_qa


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


def _invoice(db, **kwargs):
    defaults = dict(file_path="/x.pdf", source_filename="x.pdf", status=InvoiceStatus.PARSED)
    db.add(Invoice(**{**defaults, **kwargs}))
    db.commit()


# --- Yönlendirme ------------------------------------------------------------


@pytest.mark.parametrize(
    "question",
    [
        "Efferon hastaların laktat seviyesini düşürür mü",
        "Bu ürün sepsis hastalarında SOFA skorunu etkiliyor mu",
        "Hangi hastalarda hemoperfüzyon endikedir",
        "Seramon chordae loop implantasyonunda başarı oranı nedir",
        "Ürünün yan etkileri neler",
    ],
)
def test_clinical_questions_never_go_to_the_data_path(db, question):
    """'ürün' ve 'hastane' gibi zayıf kelimeler klinik sorularda geçiyor;
    yönlendirme onlara takılmamalı."""
    assert business_qa.detect(db, question) is None


@pytest.mark.parametrize(
    "question,topic",
    [
        ("Bu ay ne kadar fatura kestik", "fatura"),
        ("Geçen ay ciromuz neydi", "fatura"),
        ("Vadesi geçen faturalar ne durumda", "fatura"),
        ("Stokta kaç adet var", "stok"),
        ("SKT'si yaklaşan ürünler neler", "stok"),
        ("Hedefler ne durumda", "hedef"),
        ("Bu hafta kaç check-in yapıldı", "saha"),
    ],
)
def test_business_questions_are_recognised(db, question, topic):
    detected = business_qa.detect(db, question)
    assert detected is not None, question
    assert detected.topic == topic


def test_detection_survives_missing_turkish_characters(db):
    """Telefondan Türkçe karakter kullanmadan yazanlar var."""
    assert business_qa.detect(db, "bu ay ne kadar fatura kestik").topic == "fatura"
    assert business_qa.detect(db, "stokta kac adet var").topic == "stok"


# --- Dönem çözümleme --------------------------------------------------------


def test_periods_are_parsed_from_turkish(db):
    today = date(2026, 8, 18)

    assert business_qa.parse_period("bu ay", today).start == date(2026, 8, 1)

    last_month = business_qa.parse_period("gecen ay", today)
    assert (last_month.start, last_month.end) == (date(2026, 7, 1), date(2026, 7, 31))

    year = business_qa.parse_period("bu yil", today)
    assert (year.start, year.end) == (date(2026, 1, 1), today)

    assert business_qa.parse_period("bugun", today).start == today


def test_january_rolls_the_year_back_correctly(db):
    """Ocak'ta 'geçen ay' bir önceki yılın aralığı."""
    period = business_qa.parse_period("gecen ay", date(2026, 1, 15))
    assert (period.start, period.end) == (date(2025, 12, 1), date(2025, 12, 31))


def test_a_month_that_has_not_arrived_means_last_year(db):
    """Ağustos'ta 'aralık' denince gelecek aralık kastedilmez."""
    period = business_qa.parse_period("aralik", date(2026, 8, 18))
    assert period.start.year == 2025


def test_unspecified_period_defaults_to_this_month(db):
    period = business_qa.parse_period("ne kadar fatura kestik", date(2026, 8, 18))
    assert period.label == "bu ay"


# --- Cevaplar ---------------------------------------------------------------


def test_currencies_are_reported_separately_never_summed(client, admin, db):
    today = date.today()
    _invoice(db, amount=1000, currency="TRY", invoice_date=today)
    _invoice(db, amount=250, currency="USD", invoice_date=today)

    q = business_qa.detect(db, "bu ay ne kadar fatura kestik")
    answer = business_qa.answer(db, q)

    assert "1.000,00 TRY" in answer
    assert "250,00 USD" in answer
    assert "1250" not in answer.replace(".", "").replace(",", "")


def test_the_answer_always_states_the_period_it_used(client, admin, db):
    """Varsayılan dönem bir tahmin; hangi aralığın kullanıldığı yazılmazsa
    yönetici başka bir aralıkla eşleştirebilir."""
    q = business_qa.detect(db, "ne kadar fatura kestik")
    answer = business_qa.answer(db, q)

    assert "bu ay" in answer
    today = date.today()
    assert today.strftime("%d.%m.%Y") in answer


def test_paid_invoices_stay_out_of_the_due_answer(client, admin, db):
    today = date.today()
    _invoice(db, amount=100, due_date=today - timedelta(days=3))
    _invoice(db, amount=900, due_date=today - timedelta(days=3), status=InvoiceStatus.PAID)

    q = business_qa.detect(db, "vadesi gecen faturalar")
    answer = business_qa.answer(db, q)

    assert "100,00 TRY" in answer
    assert "900" not in answer


def test_a_named_counterparty_narrows_the_answer(client, admin, db):
    today = date.today()
    _invoice(db, amount=500, invoice_date=today, counterparty="Acıbadem Maslak")
    _invoice(db, amount=700, invoice_date=today, counterparty="Medicana")

    q = business_qa.detect(db, "bu ay Acıbadem Maslak'a ne kadar fatura kestik")

    assert q.counterparty == "Acıbadem Maslak"
    answer = business_qa.answer(db, q)
    assert "500,00 TRY" in answer
    assert "700" not in answer


def test_stock_question_about_a_product_breaks_down_by_location(client, admin, db):
    hospital = Hospital(name="Test Hastanesi")
    product = Product(name="Efferon LPS", reference_no="R1")
    db.add_all([hospital, product])
    db.commit()
    db.add_all([
        StockItem(product_id=product.id, lot_no="L1", quantity=4, status=StockItemStatus.IN_STOCK),
        StockItem(product_id=product.id, lot_no="L2", quantity=6,
                  status=StockItemStatus.AT_HOSPITAL, hospital_id=hospital.id),
    ])
    db.commit()

    q = business_qa.detect(db, "Efferon LPS stokta kaç adet var")
    answer = business_qa.answer(db, q)

    assert "10 adet" in answer
    assert "Depoda: 4" in answer
    assert "Test Hastanesi: 6" in answer


def test_stock_question_about_a_hospital_lists_its_products(client, admin, db):
    hospital = Hospital(name="Medicana Ankara")
    product = Product(name="Seramon Loop", reference_no="R2")
    db.add_all([hospital, product])
    db.commit()
    db.add(StockItem(product_id=product.id, lot_no="L1", quantity=3,
                     status=StockItemStatus.AT_HOSPITAL, hospital_id=hospital.id))
    db.commit()

    q = business_qa.detect(db, "Medicana Ankara stokta neler var")
    answer = business_qa.answer(db, q)

    assert "Medicana Ankara" in answer
    assert "Seramon Loop: 3" in answer


def test_target_question_reports_progress(client, admin, db):
    today = date.today()
    admin_user = db.query(User).filter(User.email == "admin@test.com").first()
    db.add(SalesTarget(title="Aylık satış", target_quantity=10, manual_progress=4,
                       period_start=today, period_end=today + timedelta(days=10),
                       created_by_user_id=admin_user.id))
    db.commit()

    q = business_qa.detect(db, "hedefler ne durumda")
    answer = business_qa.answer(db, q)

    assert "Aylık satış" in answer
    assert "4/10" in answer
    assert "%40" in answer


def test_field_question_counts_checkins(client, admin, db):
    hospital = Hospital(name="H1")
    db.add(hospital)
    db.commit()
    admin_user = db.query(User).filter(User.email == "admin@test.com").first()
    db.add(CheckIn(user_id=admin_user.id, hospital_id=hospital.id, photo_path="a.jpg",
                   checked_in_at=datetime.utcnow()))
    db.commit()

    q = business_qa.detect(db, "bu hafta kaç ziyaret yapıldı")
    answer = business_qa.answer(db, q)

    assert "1 check-in" in answer


def test_empty_data_answers_plainly_instead_of_failing(client, admin, db):
    q = business_qa.detect(db, "bu ay ne kadar fatura kestik")
    assert "kayıt yok" in business_qa.answer(db, q)


# --- Asistan akışına bağlanma ----------------------------------------------


def test_chat_answers_a_business_question_without_calling_the_model(client, admin, db, monkeypatch):
    """Rakamlar modele yazdırılmıyor; Qwen bu yola hiç girmemeli."""
    from app.services import rag

    def explode(*args, **kwargs):
        raise AssertionError("iş verisi sorusunda model çağrılmamalı")

    monkeypatch.setattr(rag, "ask_qwen", explode)
    _invoice(db, amount=1500, invoice_date=date.today())

    r = client.post("/assistant/chat", json={"question": "bu ay ne kadar fatura kestik"}, headers=admin)

    assert r.status_code == 200
    body = r.json()
    assert body["was_answered"] is True
    assert "1.500,00 TRY" in body["answer"]
    assert body["sources"] == []


def test_timing_diagnostics_show_the_business_route(client, admin, db):
    r = client.post(
        "/assistant/timing-diagnostics",
        json={"question": "hedefler ne durumda"},
        headers=admin,
    )
    assert r.status_code == 200
    # Konu bilgisi "kaynaklar" bölümünde: süre değil, yönlendirme kararı.
    assert r.json()["kaynaklar"]["is_verisi_konusu"] == "hedef"

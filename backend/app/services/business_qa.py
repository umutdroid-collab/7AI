"""Asistanın şirket verisi sorularını cevaplaması ("bu ay ne kadar fatura
kestik", "hangi hastanede kaç adet var").

Üç tasarım kararı, üçü de bilinçli:

**1. Rakamlar modele yazdırılmıyor.** Sorgu da cevap da deterministik.
Qwen'e "1.234.567,89 TL" gibi bir rakamı paraflattırmak yuvarlama ve uydurma
riski demek; finansal bir sayının yanlış çıkması, cevap alamamaktan çok daha
kötü. Model bu yola hiç girmiyor — yan faydası: cevap anında geliyor, klinik
yoldaki 8-14 saniye yok.

**2. Yönlendirme muhafazakâr.** Soru ancak GÜÇLÜ bir iş sinyali taşıyorsa bu
yola giriyor ("fatura", "ciro", "vade", "hedef", "stokta", "kaç adet").
"ürün", "hastane" gibi zayıf kelimeler klinik sorularda da geçiyor ("Efferon
ürünü SOFA skorunu düşürür mü") ve onları kaçırmak asıl özelliği bozardı.
Şüphede kalınca klinik yola düşülür: kaçırılan bir iş sorusu can sıkar,
kaçırılan bir klinik soru özelliği bozar.

**3. Dönem her cevapta yazılı.** "Bu ay 1.2 milyon" cümlesi hangi tarih
aralığını kastettiğini söylemezse yöneticinin kafasında başka bir aralıkla
eşleşebilir. Hesabın kapsadığı aralık her zaman açıkça belirtiliyor.

Veri EvoBulut'tan saatte bir senkronize edilen yerel veritabanından okunuyor;
canlı API çağrısı yapılmıyor. Sebep: aynı veri zaten elimizde, canlı çağrı
saniyeler ekler ve EvoBulut erişilemezse cevap hiç gelmez. Son bir saatte
kesilmiş faturaları da görmek gerekirse `POST /invoices/evobulut-sync`
senkronizasyonu elle tetikler.
"""

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Hospital, Invoice, Product, SalesTarget, StockItem, StockItemStatus
from app.services import metrics

settings = get_settings()

MONTHS = [
    "ocak", "subat", "mart", "nisan", "mayis", "haziran",
    "temmuz", "agustos", "eylul", "ekim", "kasim", "aralik",
]


def normalize(text: str) -> str:
    """Türkçe karakterleri sadeleştirip küçük harfe indirir.

    Kullanıcı "faturaları" da yazabiliyor "FATURA" da; ayrıca telefondan
    Türkçe karakter kullanmadan yazanlar var ("kac adet").
    """
    lowered = text.replace("İ", "i").replace("I", "ı").lower()
    return (
        lowered.replace("ı", "i").replace("ş", "s").replace("ğ", "g")
        .replace("ü", "u").replace("ö", "o").replace("ç", "c")
    )


# Güçlü sinyaller: klinik bir soruda geçme ihtimali yok denecek kadar az.
INVOICE_WORDS = ("fatura", "ciro", "tahsilat", "vade", "alacak", "kestik", "kesilen")
DUE_WORDS = ("vade", "odenmemis", "odenmedi", "gecikmis", "geciken", "alacak", "borc")
STOCK_WORDS = ("stok", "stokta", "kac adet", "kac tane", "depoda", "aracta", "skt", "miat")
TARGET_WORDS = ("hedef",)
FIELD_WORDS = ("check-in", "checkin", "ziyaret", "saha raporu")


@dataclass
class Period:
    start: date
    end: date
    label: str


@dataclass
class BusinessQuestion:
    topic: str
    period: Period
    counterparty: str | None = None
    product: Product | None = None
    hospital: Hospital | None = None
    due_only: bool = False
    matched: list[str] = field(default_factory=list)


def _month_range(year: int, month: int) -> tuple[date, date]:
    start = date(year, month, 1)
    end = date(year + (month == 12), (month % 12) + 1, 1) - timedelta(days=1)
    return start, end


def parse_period(text: str, today: date) -> Period:
    """Dönemi metinden çıkarır; bulunamazsa bu ay.

    Varsayılanın "bu ay" olması bir tahmin — bu yüzden cevapta hangi aralığın
    kullanıldığı her zaman yazılıyor, kullanıcı yanlışsa düzeltebilsin.
    """
    if "bugun" in text:
        return Period(today, today, "bugün")
    if "dun" in text:
        yesterday = today - timedelta(days=1)
        return Period(yesterday, yesterday, "dün")
    if "bu hafta" in text:
        return Period(today - timedelta(days=today.weekday()), today, "bu hafta")
    if "son 7 gun" in text or "son bir hafta" in text:
        return Period(today - timedelta(days=6), today, "son 7 gün")
    if "son 30 gun" in text:
        return Period(today - timedelta(days=29), today, "son 30 gün")
    if "gecen ay" in text:
        month = today.month - 1 or 12
        year = today.year - (today.month == 1)
        start, end = _month_range(year, month)
        return Period(start, end, f"geçen ay ({MONTHS[month - 1]} {year})")
    if "gecen yil" in text:
        return Period(date(today.year - 1, 1, 1), date(today.year - 1, 12, 31), f"{today.year - 1}")
    if "bu yil" in text:
        return Period(date(today.year, 1, 1), today, f"{today.year}")

    for index, name in enumerate(MONTHS, start=1):
        if name in text:
            # "mart" dendiğinde henüz gelmemiş bir ay kastedilmez; geçen yılın
            # aynı ayı daha olası.
            year = today.year if index <= today.month else today.year - 1
            start, end = _month_range(year, index)
            return Period(start, end, f"{name} {year}")

    start, _ = _month_range(today.year, today.month)
    return Period(start, today, "bu ay")


def _longest_match(text: str, candidates: list[tuple[str, object]]) -> object | None:
    """Metinde geçen en uzun adı seçer.

    Uzun olan kazanmalı: "Acıbadem Maslak" ile "Acıbadem" birlikte kayıtlıysa
    ve kullanıcı ilkini yazdıysa, kısa olanı seçmek yanlış hastaneyi getirir.
    """
    hits = [(name, obj) for name, obj in candidates if name and name in text]
    if not hits:
        return None
    return max(hits, key=lambda pair: len(pair[0]))[1]


def detect(db: Session, question: str, today: date | None = None) -> BusinessQuestion | None:
    """Soru şirket verisi sorusuysa çözümlenmiş halini, değilse None döner."""
    today = today or date.today()
    text = normalize(question)

    matched = [w for w in INVOICE_WORDS + STOCK_WORDS + TARGET_WORDS + FIELD_WORDS if w in text]
    if not matched:
        return None

    period = parse_period(text, today)

    if any(w in text for w in TARGET_WORDS):
        return BusinessQuestion("hedef", period, matched=matched)
    if any(w in text for w in FIELD_WORDS):
        return BusinessQuestion("saha", period, matched=matched)

    if any(w in text for w in STOCK_WORDS):
        products = [(normalize(p.name), p) for p in db.query(Product).all()]
        hospitals = [(normalize(h.name), h) for h in db.query(Hospital).all()]
        return BusinessQuestion(
            "stok",
            period,
            product=_longest_match(text, products),
            hospital=_longest_match(text, hospitals),
            matched=matched,
        )

    counterparties = [
        (normalize(c), c)
        for (c,) in db.query(Invoice.counterparty).distinct().all()
        if c
    ]
    return BusinessQuestion(
        "fatura",
        period,
        counterparty=_longest_match(text, counterparties),
        due_only=any(w in text for w in DUE_WORDS),
        matched=matched,
    )


def _amount(value: float, currency: str) -> str:
    """1234567.5 → '1.234.567,50 TRY' (tr-TR biçimi)."""
    formatted = f"{value:,.2f}".replace(",", "#").replace(".", ",").replace("#", ".")
    return f"{formatted} {currency}"


def _totals_line(rows: list[dict]) -> str:
    if not rows:
        return "kayıt yok"
    # Para birimleri ayrı ayrı - toplanmaları anlamsız olurdu.
    return "; ".join(f"{_amount(r['tutar'], r['para_birimi'])} ({r['adet']} fatura)" for r in rows)


def _invoice_answer(db: Session, q: BusinessQuestion, today: date) -> str:
    filters = []
    who = ""
    if q.counterparty:
        filters.append(Invoice.counterparty == q.counterparty)
        who = f" — {q.counterparty}"

    if q.due_only:
        overdue = metrics.invoice_totals(db, metrics.UNPAID, Invoice.due_date < today, *filters)
        upcoming = metrics.invoice_totals(
            db, metrics.UNPAID, Invoice.due_date >= today,
            Invoice.due_date <= today + timedelta(days=30), *filters,
        )
        return (
            f"**Ödenmemiş faturalar{who}** (bugün: {today.strftime('%d.%m.%Y')})\n\n"
            f"- Vadesi geçen: {_totals_line(overdue)}\n"
            f"- Önümüzdeki 30 gün: {_totals_line(upcoming)}\n\n"
            "Ödenmiş faturalar bu rakamlara dahil değildir."
        )

    issued = metrics.invoice_totals(
        db, Invoice.invoice_date >= q.period.start, Invoice.invoice_date <= q.period.end, *filters
    )
    return (
        f"**Kesilen faturalar{who}** — {q.period.label} "
        f"({q.period.start.strftime('%d.%m.%Y')} – {q.period.end.strftime('%d.%m.%Y')})\n\n"
        f"{_totals_line(issued)}\n\n"
        "Para birimleri ayrı gösterilir; farklı kurlar toplanmaz."
    )


def _stock_answer(db: Session, q: BusinessQuestion, today: date) -> str:
    if q.product:
        filters = {"product_id": q.product.id}
        in_stock = metrics.stock_quantity(db, StockItemStatus.IN_STOCK, **filters)
        at_hospital = metrics.stock_quantity(db, StockItemStatus.AT_HOSPITAL, **filters)
        in_vehicle = metrics.stock_quantity(db, StockItemStatus.IN_VEHICLE, **filters)

        rows = (
            db.query(Hospital.name, StockItem.quantity)
            .join(StockItem, StockItem.hospital_id == Hospital.id)
            .filter(
                StockItem.product_id == q.product.id,
                StockItem.status == StockItemStatus.AT_HOSPITAL,
            )
            .all()
        )
        by_hospital: dict[str, int] = {}
        for name, quantity in rows:
            by_hospital[name] = by_hospital.get(name, 0) + quantity

        lines = [
            f"**{q.product.name}** (toplam {in_stock + at_hospital + in_vehicle} adet)",
            "",
            f"- Depoda: {in_stock}",
            f"- Hastanelerde: {at_hospital}",
            f"- Araçlarda: {in_vehicle}",
        ]
        if by_hospital:
            lines.append("")
            lines += [
                f"- {name}: {qty}"
                for name, qty in sorted(by_hospital.items(), key=lambda kv: -kv[1])
            ]
        return "\n".join(lines)

    if q.hospital:
        rows = (
            db.query(Product.name, StockItem.quantity)
            .join(StockItem, StockItem.product_id == Product.id)
            .filter(
                StockItem.hospital_id == q.hospital.id,
                StockItem.status == StockItemStatus.AT_HOSPITAL,
            )
            .all()
        )
        by_product: dict[str, int] = {}
        for name, quantity in rows:
            by_product[name] = by_product.get(name, 0) + quantity
        if not by_product:
            return f"**{q.hospital.name}** hastanesinde konsinye stok görünmüyor."
        listing = "\n".join(
            f"- {name}: {qty}" for name, qty in sorted(by_product.items(), key=lambda kv: -kv[1])
        )
        return f"**{q.hospital.name}** ({sum(by_product.values())} adet)\n\n{listing}"

    if any(w in " ".join(q.matched) for w in ("skt", "miat")):
        limit = today + timedelta(days=settings.skt_warning_days)
        items = metrics.expiring_stock(db, limit, limit=10)
        if not items:
            return f"Önümüzdeki {settings.skt_warning_days} gün içinde SKT'si dolacak ürün yok."
        listing = "\n".join(
            f"- {product.name} (lot {item.lot_no}) — {item.skt.strftime('%d.%m.%Y')}, "
            f"{(item.skt - today).days} gün, {hospital.name if hospital else 'Depo/Araç'}"
            for item, product, hospital in items
        )
        return f"**SKT'si yaklaşanlar**\n\n{listing}"

    in_stock = metrics.stock_quantity(db, StockItemStatus.IN_STOCK)
    at_hospital = metrics.stock_quantity(db, StockItemStatus.AT_HOSPITAL)
    in_vehicle = metrics.stock_quantity(db, StockItemStatus.IN_VEHICLE)
    hospitals = metrics.stock_by_hospital(db, limit=10)
    listing = "\n".join(f"- {name}: {qty}" for name, qty in hospitals)
    return (
        f"**Stok durumu** (toplam {in_stock + at_hospital + in_vehicle} adet)\n\n"
        f"- Depoda: {in_stock}\n- Hastanelerde: {at_hospital}\n- Araçlarda: {in_vehicle}"
        + (f"\n\n**Hastane dağılımı**\n\n{listing}" if listing else "")
    )


def _target_answer(db: Session, today: date) -> str:
    from app.routers.sales_targets import _with_progress

    active = (
        db.query(SalesTarget)
        .filter(SalesTarget.period_start <= today, SalesTarget.period_end >= today)
        .all()
    )
    if not active:
        return "Şu anda süren bir hedef yok."

    lines = []
    for target in sorted(active, key=lambda t: t.period_end):
        out = _with_progress(target, db)
        title = out.title or (target.product.name if target.product else "Hedef")
        who = target.assigned_user.full_name if target.assigned_user else "Tüm ekip"
        percent = round(out.progress * 100 / out.target_quantity) if out.target_quantity else 0
        lines.append(
            f"- **{title}** ({who}): {out.progress}/{out.target_quantity} (%{percent}) — "
            f"{(target.period_end - today).days} gün kaldı"
        )
    return "**Süren hedefler**\n\n" + "\n".join(lines)


def _field_answer(db: Session, q: BusinessQuestion) -> str:
    since = datetime.combine(q.period.start, datetime.min.time())
    total, hospitals, per_user = metrics.checkin_counts(db, since)
    if total == 0:
        return f"{q.period.label.capitalize()} hiç check-in kaydı yok."
    listing = "\n".join(f"- {name}: {count}" for name, count in per_user)
    return (
        f"**Saha aktivitesi** — {q.period.label}\n\n"
        f"{total} check-in, {hospitals} farklı hastane\n\n{listing}"
    )


def answer(db: Session, q: BusinessQuestion, today: date | None = None) -> str:
    today = today or date.today()
    if q.topic == "fatura":
        return _invoice_answer(db, q, today)
    if q.topic == "stok":
        return _stock_answer(db, q, today)
    if q.topic == "hedef":
        return _target_answer(db, today)
    return _field_answer(db, q)

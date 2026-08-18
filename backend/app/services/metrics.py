"""Pano ve asistanın ortak hesap katmanı.

İkisi de aynı soruları soruyor ("bu ay ne kadar fatura kestik", "hastanede
kaç adet var"). Hesap iki yerde ayrı yazılsaydı zamanla ayrışır ve aynı
soruya iki farklı rakam dönerdi — bir yönetici panosunda bunun bedeli
yüksek. Kurallar tek yerde:

- **Para birimleri toplanmaz.** Faturalar TRY/USD/EUR karışık geliyor; tek
  bir "toplam" uydurma bir sayı olurdu.
- **Ödenmiş faturalar vade rakamlarına girmez** — artık yapılacak bir iş
  değiller (fatura listesindeki kuralla aynı).
- **Satır değil `quantity` toplanır** — bir stok satırı birden fazla adet
  taşıyabiliyor.
"""

from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import CheckIn, Invoice, InvoiceStatus, StockItem, StockItemStatus

# Sahada ya da depoda duran, yani hâlâ takip edilen kalemler. Kullanılmış veya
# iade edilmişlerin SKT'si ve konumu artık kimseyi ilgilendirmiyor.
LIVE_STATUSES = (
    StockItemStatus.IN_STOCK,
    StockItemStatus.AT_HOSPITAL,
    StockItemStatus.IN_VEHICLE,
)

UNPAID = Invoice.status != InvoiceStatus.PAID


def invoice_totals(db: Session, *filters) -> list[dict]:
    """Para birimi bazında (tutar, adet); tutara göre büyükten küçüğe.

    Tutarı okunamamış faturalar toplama girmez — `amount` boş olabiliyor.
    """
    rows = (
        db.query(Invoice.currency, func.sum(Invoice.amount), func.count(Invoice.id))
        .filter(Invoice.amount.isnot(None), *filters)
        .group_by(Invoice.currency)
        .all()
    )
    return sorted(
        [
            {"para_birimi": currency or "TRY", "tutar": round(total or 0, 2), "adet": count}
            for currency, total, count in rows
        ],
        key=lambda r: r["tutar"],
        reverse=True,
    )


def stock_quantity(db: Session, *statuses, **filters) -> int:
    """Verilen durumlardaki toplam adet (satır sayısı değil)."""
    query = db.query(func.sum(StockItem.quantity)).filter(StockItem.status.in_(statuses))
    for column, value in filters.items():
        query = query.filter(getattr(StockItem, column) == value)
    return int(query.scalar() or 0)


def stock_by_hospital(db: Session, limit: int | None = None) -> list[tuple[str, int]]:
    from app.models import Hospital

    query = (
        db.query(Hospital.name, func.sum(StockItem.quantity))
        .join(StockItem, StockItem.hospital_id == Hospital.id)
        .filter(StockItem.status == StockItemStatus.AT_HOSPITAL)
        .group_by(Hospital.id)
        .order_by(func.sum(StockItem.quantity).desc())
    )
    if limit:
        query = query.limit(limit)
    return [(name, int(qty or 0)) for name, qty in query.all()]


def stock_by_vehicle(db: Session) -> list[tuple[str, int]]:
    from app.models import User

    rows = (
        db.query(User.full_name, func.sum(StockItem.quantity))
        .join(StockItem, StockItem.carried_by_user_id == User.id)
        .filter(StockItem.status == StockItemStatus.IN_VEHICLE)
        .group_by(User.id)
        .order_by(func.sum(StockItem.quantity).desc())
        .all()
    )
    return [(name, int(qty or 0)) for name, qty in rows]


def expiring_stock(db: Session, until: date, limit: int | None = None) -> list[tuple]:
    """(StockItem, Product, Hospital|None) — SKT'si `until` tarihine kadar
    olan, hâlâ takip edilen kalemler."""
    from app.models import Hospital, Product

    query = (
        db.query(StockItem, Product, Hospital)
        .join(Product, StockItem.product_id == Product.id)
        .outerjoin(Hospital, StockItem.hospital_id == Hospital.id)
        .filter(
            StockItem.status.in_(LIVE_STATUSES),
            StockItem.skt.isnot(None),
            StockItem.skt <= until,
        )
        .order_by(StockItem.skt)
    )
    if limit:
        query = query.limit(limit)
    return query.all()


def checkin_counts(db: Session, since) -> tuple[int, int, list[tuple[str, int]]]:
    """(toplam, ziyaret edilen hastane sayısı, çalışan bazlı dağılım)."""
    from app.models import User

    window = CheckIn.checked_in_at >= since
    total = db.query(CheckIn).filter(window).count()
    hospitals = (
        db.query(func.count(func.distinct(CheckIn.hospital_id))).filter(window).scalar() or 0
    )
    per_user = (
        db.query(User.full_name, func.count(CheckIn.id))
        .join(CheckIn, CheckIn.user_id == User.id)
        .filter(window)
        .group_by(User.id)
        .order_by(func.count(CheckIn.id).desc())
        .all()
    )
    return total, hospitals, [(name, count) for name, count in per_user]

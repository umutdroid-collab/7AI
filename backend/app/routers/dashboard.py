"""Yönetici panosu: beş sekmeye dağılmış rakamların tek ekranda özeti.

Tasarım kararları:

- **Para birimleri toplanmaz.** Faturalar TRY/USD/EUR karışık geliyor; tek bir
  "toplam" göstermek yanlış olurdu. Her tutar para birimi bazında ayrı döner.
- **Ödenmiş faturalar vade rakamlarına girmez** - artık yapılacak bir iş
  değiller (fatura listesindeki kuralla aynı, ikisi ayrışmasın).
- **Adet değil miktar sayılır.** `StockItem.quantity` bire eşit olmak zorunda
  değil; satır saymak yanıltıcı olurdu.
- Hedef ilerlemesi `sales_targets._with_progress` ile hesaplanır. Kopyalamak
  yerine tek kaynaktan çağrılıyor: hesap ürüne bağlı/manuel ayrımı, katkı
  dağılımı ve elle düzeltme içeriyor, iki yerde tutulursa zamanla ayrışır.
"""

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.deps import require_admin
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

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
settings = get_settings()

# Panoda liste halinde gösterilen kırılımların üst sınırı: pano bir özet,
# tam liste ilgili sekmede zaten var.
TOP_N = 8


def _by_currency(rows) -> list[dict]:
    """(para_birimi, tutar, adet) satırlarını tutara göre büyükten küçüğe."""
    return sorted(
        [
            {"para_birimi": currency or "TRY", "tutar": round(total or 0, 2), "adet": count}
            for currency, total, count in rows
        ],
        key=lambda r: r["tutar"],
        reverse=True,
    )


def _invoice_totals(db: Session, *args) -> list[dict]:
    query = (
        db.query(Invoice.currency, func.sum(Invoice.amount), func.count(Invoice.id))
        .filter(Invoice.amount.isnot(None), *args)
        .group_by(Invoice.currency)
    )
    return _by_currency(query.all())


def _invoices(db: Session, today: date) -> dict:
    unpaid = Invoice.status != InvoiceStatus.PAID
    month_start = today.replace(day=1)

    return {
        # Kesim tarihi bu ay olanlar - ödenmiş olsun olmasın, bu bir ciro
        # göstergesi, alacak göstergesi değil.
        "bu_ay_kesilen": _invoice_totals(db, Invoice.invoice_date >= month_start),
        "vadesi_gecen": _invoice_totals(db, unpaid, Invoice.due_date < today),
        "yaklasan_7_gun": _invoice_totals(
            db, unpaid, Invoice.due_date >= today, Invoice.due_date <= today + timedelta(days=7)
        ),
        "yaklasan_30_gun": _invoice_totals(
            db, unpaid, Invoice.due_date >= today, Invoice.due_date <= today + timedelta(days=30)
        ),
        "kontrol_gerekli": db.query(Invoice)
        .filter(Invoice.status == InvoiceStatus.NEEDS_REVIEW)
        .count(),
    }


def _stock(db: Session, today: date) -> dict:
    hospital_rows = (
        db.query(Hospital.name, func.sum(StockItem.quantity))
        .join(StockItem, StockItem.hospital_id == Hospital.id)
        .filter(StockItem.status == StockItemStatus.AT_HOSPITAL)
        .group_by(Hospital.id)
        .order_by(func.sum(StockItem.quantity).desc())
        .limit(TOP_N)
        .all()
    )
    vehicle_rows = (
        db.query(User.full_name, func.sum(StockItem.quantity))
        .join(StockItem, StockItem.carried_by_user_id == User.id)
        .filter(StockItem.status == StockItemStatus.IN_VEHICLE)
        .group_by(User.id)
        .order_by(func.sum(StockItem.quantity).desc())
        .all()
    )

    # SKT'si yaklaşanlar: yalnızca hâlâ sahada/depoda olanlar. Kullanılmış ya
    # da iade edilmiş bir ürünün son kullanma tarihi artık kimseyi ilgilendirmez.
    live = StockItem.status.in_(
        [StockItemStatus.IN_STOCK, StockItemStatus.AT_HOSPITAL, StockItemStatus.IN_VEHICLE]
    )
    limit_date = today + timedelta(days=settings.skt_warning_days)
    expiring = (
        db.query(StockItem, Product, Hospital)
        .join(Product, StockItem.product_id == Product.id)
        .outerjoin(Hospital, StockItem.hospital_id == Hospital.id)
        .filter(live, StockItem.skt.isnot(None), StockItem.skt <= limit_date)
        .order_by(StockItem.skt)
        .limit(TOP_N)
        .all()
    )

    def _quantity(*statuses) -> int:
        total = (
            db.query(func.sum(StockItem.quantity))
            .filter(StockItem.status.in_(statuses))
            .scalar()
        )
        return int(total or 0)

    return {
        "depoda": _quantity(StockItemStatus.IN_STOCK),
        "hastanelerde_toplam": _quantity(StockItemStatus.AT_HOSPITAL),
        "araclarda_toplam": _quantity(StockItemStatus.IN_VEHICLE),
        "hastane_dagilimi": [{"hastane": name, "adet": int(qty or 0)} for name, qty in hospital_rows],
        "arac_dagilimi": [{"calisan": name, "adet": int(qty or 0)} for name, qty in vehicle_rows],
        "skt_yaklasan": [
            {
                "urun": product.name,
                "lot_no": item.lot_no,
                "skt": item.skt.isoformat(),
                "kalan_gun": (item.skt - today).days,
                "konum": hospital.name if hospital else "Depo/Araç",
            }
            for item, product, hospital in expiring
        ],
    }


def _field(db: Session, today: date) -> dict:
    week_start = datetime.combine(today - timedelta(days=6), datetime.min.time())
    this_week = CheckIn.checked_in_at >= week_start

    per_user = (
        db.query(User.full_name, func.count(CheckIn.id))
        .join(CheckIn, CheckIn.user_id == User.id)
        .filter(this_week)
        .group_by(User.id)
        .order_by(func.count(CheckIn.id).desc())
        .all()
    )
    return {
        "son_7_gun_checkin": db.query(CheckIn).filter(this_week).count(),
        "ziyaret_edilen_hastane": db.query(func.count(func.distinct(CheckIn.hospital_id)))
        .filter(this_week)
        .scalar()
        or 0,
        "calisan_dagilimi": [{"calisan": name, "adet": count} for name, count in per_user],
    }


def _targets(db: Session, today: date) -> list[dict]:
    from app.routers.sales_targets import _with_progress

    # Yalnızca dönemi süren hedefler: pano "şu an ne durumdayız" sorusunu
    # cevaplıyor, geçmiş dönemler Hedefler sekmesinde duruyor.
    active = (
        db.query(SalesTarget)
        .filter(SalesTarget.period_start <= today, SalesTarget.period_end >= today)
        .all()
    )

    rows = []
    for target in active:
        out = _with_progress(target, db)
        rows.append(
            {
                "baslik": out.title or (target.product.name if target.product else "Hedef"),
                "calisan": target.assigned_user.full_name if target.assigned_user else "Tüm ekip",
                "hedef": out.target_quantity,
                "ilerleme": out.progress,
                "yuzde": min(100, round(out.progress * 100 / out.target_quantity)) if out.target_quantity else 0,
                "kalan_gun": (target.period_end - today).days,
            }
        )
    return sorted(rows, key=lambda r: r["yuzde"])


@router.get("/summary")
def dashboard_summary(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    """Panonun tüm rakamları tek çağrıda.

    Tek uç olmasının sebebi: pano açılışında dört ayrı istek atmak mobil
    veride hem yavaş hem de kısmi yüklenmiş bir ekran demekti.
    """
    today = date.today()
    return {
        "tarih": today.isoformat(),
        "faturalar": _invoices(db, today),
        "stok": _stock(db, today),
        "saha": _field(db, today),
        "hedefler": _targets(db, today),
    }

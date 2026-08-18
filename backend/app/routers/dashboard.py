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
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.deps import require_admin
from app.services import metrics
from app.models import Invoice, InvoiceStatus, SalesTarget, StockItemStatus, User

router = APIRouter(prefix="/dashboard", tags=["dashboard"])
settings = get_settings()

# Panoda liste halinde gösterilen kırılımların üst sınırı: pano bir özet,
# tam liste ilgili sekmede zaten var.
TOP_N = 8


def _invoices(db: Session, today: date) -> dict:
    unpaid = metrics.UNPAID
    month_start = today.replace(day=1)

    return {
        # Kesim tarihi bu ay olanlar - ödenmiş olsun olmasın, bu bir ciro
        # göstergesi, alacak göstergesi değil.
        "bu_ay_kesilen": metrics.invoice_totals(db, Invoice.invoice_date >= month_start),
        "vadesi_gecen": metrics.invoice_totals(db, unpaid, Invoice.due_date < today),
        "yaklasan_7_gun": metrics.invoice_totals(
            db, unpaid, Invoice.due_date >= today, Invoice.due_date <= today + timedelta(days=7)
        ),
        "yaklasan_30_gun": metrics.invoice_totals(
            db, unpaid, Invoice.due_date >= today, Invoice.due_date <= today + timedelta(days=30)
        ),
        "kontrol_gerekli": db.query(Invoice)
        .filter(Invoice.status == InvoiceStatus.NEEDS_REVIEW)
        .count(),
    }


def _stock(db: Session, today: date) -> dict:
    expiring = metrics.expiring_stock(
        db, today + timedelta(days=settings.skt_warning_days), limit=TOP_N
    )

    return {
        "depoda": metrics.stock_quantity(db, StockItemStatus.IN_STOCK),
        "hastanelerde_toplam": metrics.stock_quantity(db, StockItemStatus.AT_HOSPITAL),
        "araclarda_toplam": metrics.stock_quantity(db, StockItemStatus.IN_VEHICLE),
        "hastane_dagilimi": [
            {"hastane": name, "adet": qty} for name, qty in metrics.stock_by_hospital(db, limit=TOP_N)
        ],
        "arac_dagilimi": [
            {"calisan": name, "adet": qty} for name, qty in metrics.stock_by_vehicle(db)
        ],
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
    total, hospitals, per_user = metrics.checkin_counts(db, week_start)
    return {
        "son_7_gun_checkin": total,
        "ziyaret_edilen_hastane": hospitals,
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

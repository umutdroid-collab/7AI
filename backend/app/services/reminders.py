"""Vade tarihi (fatura) ve SKT (stok) hatırlatmalarını üreten zamanlanmış işler."""

import logging
from datetime import date, datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import get_settings
from app.database import SessionLocal
from app.models import Invoice, Notification, StockItem, StockItemStatus

logger = logging.getLogger("reminders")
settings = get_settings()


def _notification_exists(db, invoice_id=None, stock_item_id=None, title=None) -> bool:
    query = db.query(Notification)
    if invoice_id is not None:
        query = query.filter(Notification.invoice_id == invoice_id)
    if stock_item_id is not None:
        query = query.filter(Notification.stock_item_id == stock_item_id)
    if title is not None:
        query = query.filter(Notification.title == title)
    return db.query(query.exists()).scalar()


def generate_invoice_due_reminders() -> None:
    db = SessionLocal()
    try:
        today = date.today()
        cutoff = today + timedelta(days=settings.invoice_reminder_days)
        invoices = db.query(Invoice).filter(
            Invoice.due_date.isnot(None), Invoice.due_date <= cutoff
        ).all()

        for invoice in invoices:
            days_left = (invoice.due_date - today).days
            if days_left < 0:
                title = f"Vadesi geçti: {invoice.invoice_number or invoice.source_filename}"
            elif days_left == 0:
                title = f"Bugün vadesi doluyor: {invoice.invoice_number or invoice.source_filename}"
            else:
                title = f"Vade yaklaşıyor ({days_left} gün): {invoice.invoice_number or invoice.source_filename}"

            if _notification_exists(db, invoice_id=invoice.id, title=title):
                continue

            amount_str = f"{invoice.amount:,.2f} {invoice.currency}" if invoice.amount else "tutar bilinmiyor"
            message = (
                f"{invoice.counterparty or 'Tedarikçi'} - {amount_str} - "
                f"Vade tarihi: {invoice.due_date.isoformat()}"
            )
            db.add(Notification(invoice_id=invoice.id, title=title, message=message))

        db.commit()
    except Exception:
        logger.exception("Fatura vade hatırlatmaları oluşturulamadı")
        db.rollback()
    finally:
        db.close()


def generate_skt_expiry_reminders() -> None:
    db = SessionLocal()
    try:
        today = date.today()
        cutoff = today + timedelta(days=settings.skt_warning_days)
        items = db.query(StockItem).filter(
            StockItem.skt <= cutoff,
            StockItem.status.in_([StockItemStatus.IN_STOCK, StockItemStatus.AT_HOSPITAL]),
        ).all()

        for item in items:
            days_left = (item.skt - today).days
            location = item.hospital.name if item.hospital else "Depo"
            if days_left < 0:
                title = f"SKT geçti: {item.product.name} (Lot {item.lot_no})"
            else:
                title = f"SKT yaklaşıyor ({days_left} gün): {item.product.name} (Lot {item.lot_no})"

            if _notification_exists(db, stock_item_id=item.id, title=title):
                continue

            message = (
                f"Ref: {item.product.reference_no} - Seri: {item.serial_no or '-'} - "
                f"Konum: {location} - SKT: {item.skt.isoformat()}"
            )
            db.add(Notification(stock_item_id=item.id, title=title, message=message))

        db.commit()
    except Exception:
        logger.exception("SKT hatırlatmaları oluşturulamadı")
        db.rollback()
    finally:
        db.close()


def run_all_reminder_jobs() -> None:
    generate_invoice_due_reminders()
    generate_skt_expiry_reminders()


def start_scheduler() -> BackgroundScheduler:
    from app.services.daily_digest import send_daily_digest

    scheduler = BackgroundScheduler(timezone="Europe/Istanbul")
    scheduler.add_job(run_all_reminder_jobs, "interval", hours=6, next_run_time=datetime.now())
    # Günlük özet sabit saatte (cron) çalışır; interval işlerin aksine
    # next_run_time verilmiyor - yeniden başlatmalar fazladan e-posta
    # göndermesin diye.
    scheduler.add_job(send_daily_digest, "cron", hour=settings.digest_hour, minute=0)
    scheduler.start()
    logger.info(
        "Hatırlatma zamanlayıcısı başlatıldı (6 saatte bir; günlük özet %02d:00)",
        settings.digest_hour,
    )
    return scheduler

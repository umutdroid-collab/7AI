"""EvoBulut'ta kesilen satış faturalarını periyodik olarak çekip Fatura
Takip sistemine (Invoice tablosu) aktarır."""

import logging
import os
from datetime import date, datetime

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import get_settings
from app.database import SessionLocal
from app.models import Invoice, InvoiceStatus
from app.services.evobulut import (
    EvoBulutError,
    download_pdf_bytes,
    fetch_all_sales_invoices,
    fetch_invoice_pdf_url,
)
from app.services.pdf_compress import compress_invoice_pdf
from app.utils import unique_destination

logger = logging.getLogger("evobulut_sync")
settings = get_settings()

CURRENCY_MAP = {"₺": "TRY", "TL": "TRY", "$": "USD", "€": "EUR"}


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value.strip(), "%d.%m.%Y %H:%M:%S").date()
    except ValueError:
        return None


def _parse_float(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _invoice_number(item: dict) -> str | None:
    val = (item.get("G.a_sbelge_seri_no") or "").strip()
    if not val or val.upper() == "GÖNDERİLMEDİ":
        return None
    return val


def _counterparty(item: dict) -> str | None:
    for key in ("CARI_ADI", "TBL_REHBER.a_resmi_ad"):
        val = (item.get(key) or "").strip()
        if val:
            return val
    return None


def _currency(item: dict) -> str:
    raw = (item.get("TBL_DOV.a_adi") or "").strip()
    return CURRENCY_MAP.get(raw, raw or "TRY")


def _status(item: dict, amount: float | None) -> InvoiceStatus:
    kalan = _parse_float(item.get("Kalan"))
    if amount and amount > 0 and kalan == 0:
        return InvoiceStatus.PAID
    return InvoiceStatus.PARSED


def _download_pdf(evobulut_id: str, dest_folder: str) -> tuple[str, str] | None:
    """Başarılıysa (file_path, source_filename) döner, başarısızsa None."""
    try:
        url = fetch_invoice_pdf_url(evobulut_id)
        if not url:
            return None
        content = download_pdf_bytes(url)
        if content[:4] != b"%PDF":
            logger.warning("EvoBulut fatura %s için indirilen dosya PDF gibi görünmüyor", evobulut_id)
            return None
        os.makedirs(dest_folder, exist_ok=True)
        source_filename = f"evobulut-{evobulut_id}.pdf"
        dest_path = unique_destination(dest_folder, source_filename)
        with open(dest_path, "wb") as f:
            f.write(content)
        # Bu PDF'ler watchdog'un görmediği alt klasöre iniyor, yani
        # ingest_pdf'ten geçmiyorlar; küçültme burada ayrıca çağrılmalı.
        compress_invoice_pdf(dest_path)
        return dest_path, os.path.basename(dest_path)
    except Exception:
        logger.exception("EvoBulut fatura %s için PDF indirilemedi", evobulut_id)
        return None


def sync_invoices_from_evobulut() -> dict:
    db = SessionLocal()
    created = 0
    skipped = 0
    errors: list[str] = []
    try:
        try:
            items = fetch_all_sales_invoices(a_onay="1")
        except EvoBulutError as e:
            return {"ok": False, "message": str(e)}

        for item in items:
            evobulut_id = item.get("G.a_id")
            if not evobulut_id:
                continue

            exists = db.query(Invoice).filter(Invoice.evobulut_id == evobulut_id).first()
            if exists:
                skipped += 1
                continue

            amount = _parse_float(item.get("G.a_tutar"))
            # invoice_folder'ın kökü yerine bir alt klasöre kaydediyoruz - kök,
            # elle bırakılan PDF'ler için watchdog tarafından izleniyor
            # (recursive=False), bir alt klasör ona görünmez olur. Aksi halde
            # bu PDF hem burada hem watcher tarafından ayrı ayrı (ve daha
            # düşük güvenle, OCR ile) işlenip EvoBulut'tan gelen doğru
            # verilerin üzerine yazardı.
            pdf_result = _download_pdf(evobulut_id, os.path.join(settings.invoice_folder, "evobulut"))
            if pdf_result:
                file_path, source_filename = pdf_result
            else:
                file_path = ""
                source_filename = f"evobulut-{evobulut_id}.pdf"
                errors.append(f"Fatura {evobulut_id}: PDF indirilemedi, sadece veriler aktarıldı")

            invoice = Invoice(
                evobulut_id=evobulut_id,
                invoice_number=_invoice_number(item),
                invoice_date=_parse_date(item.get("G.a_tarih")),
                due_date=_parse_date(item.get("G.a_vtarih")),
                amount=amount,
                currency=_currency(item),
                counterparty=_counterparty(item),
                file_path=file_path,
                source_filename=source_filename,
                status=_status(item, amount),
                parse_confidence=1.0,
            )
            db.add(invoice)
            created += 1

        db.commit()
    except Exception:
        logger.exception("EvoBulut senkronizasyonu başarısız oldu")
        db.rollback()
        return {"ok": False, "message": "Senkronizasyon sırasında beklenmeyen bir hata oluştu, sunucu loglarına bakın"}
    finally:
        db.close()

    logger.info("EvoBulut senkronizasyonu: %d yeni fatura, %d zaten vardı", created, skipped)
    return {"ok": True, "created": created, "skipped": skipped, "errors": errors}


def start_evobulut_sync_scheduler() -> BackgroundScheduler | None:
    if not settings.evobulut_username or not settings.evobulut_password:
        logger.info("EVOBULUT_USERNAME/PASSWORD ayarlanmamış, EvoBulut senkronizasyonu devre dışı")
        return None
    scheduler = BackgroundScheduler(timezone="Europe/Istanbul")
    scheduler.add_job(sync_invoices_from_evobulut, "interval", hours=1, next_run_time=datetime.now())
    scheduler.start()
    logger.info("EvoBulut senkronizasyon zamanlayıcısı başlatıldı (saatte bir çalışır)")
    return scheduler

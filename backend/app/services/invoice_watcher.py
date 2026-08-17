import logging
import os
import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from app.config import get_settings
from app.database import SessionLocal
from app.models import Invoice, InvoiceStatus
from app.services.invoice_parser import parse_invoice_pdf
from app.services.pdf_compress import compress_pdf

logger = logging.getLogger("invoice_watcher")
settings = get_settings()


def _status_for(parsed_confidence: float) -> InvoiceStatus:
    return InvoiceStatus.PARSED if parsed_confidence >= 0.75 else InvoiceStatus.NEEDS_REVIEW


def ingest_pdf(pdf_path: str) -> None:
    filename = os.path.basename(pdf_path)
    db = SessionLocal()
    try:
        existing = db.query(Invoice).filter(Invoice.source_filename == filename).first()
        parsed = parse_invoice_pdf(pdf_path)
        # Okuma bittikten sonra küçültülür: elle bırakılan taramalar sayfa
        # başına birkaç MB tutuyor ve her haftalık yedeğe olduğu gibi giriyor.
        # Yükleme, toplu yükleme ve `rescan` yollarının hepsi buradan geçtiği
        # için tek bağlama noktası yeterli.
        compress_pdf(pdf_path)

        if existing:
            invoice = existing
        else:
            invoice = Invoice(file_path=pdf_path, source_filename=filename)
            db.add(invoice)

        invoice.file_path = pdf_path
        invoice.invoice_number = parsed.invoice_number
        invoice.invoice_date = parsed.invoice_date
        invoice.due_date = parsed.due_date
        invoice.amount = parsed.amount
        invoice.currency = parsed.currency
        invoice.counterparty = parsed.counterparty
        invoice.raw_text_excerpt = parsed.raw_text_excerpt
        invoice.parse_confidence = parsed.confidence
        invoice.status = _status_for(parsed.confidence)

        db.commit()
        logger.info("Fatura işlendi: %s (güven: %.2f)", filename, parsed.confidence)
    except Exception:
        logger.exception("Fatura işlenemedi: %s", filename)
        db.rollback()
    finally:
        db.close()


def scan_existing_invoices() -> None:
    folder = Path(settings.invoice_folder)
    folder.mkdir(parents=True, exist_ok=True)
    for pdf_file in folder.glob("*.pdf"):
        ingest_pdf(str(pdf_file))


class _InvoiceHandler(FileSystemEventHandler):
    def on_created(self, event):
        self._maybe_ingest(event)

    def on_modified(self, event):
        self._maybe_ingest(event)

    def _maybe_ingest(self, event):
        if event.is_directory or not event.src_path.lower().endswith(".pdf"):
            return
        # PDF henüz tamamen kopyalanıyor olabilir; boyutu stabilize olana kadar bekle.
        last_size = -1
        for _ in range(10):
            try:
                size = os.path.getsize(event.src_path)
            except OSError:
                return
            if size == last_size:
                break
            last_size = size
            time.sleep(0.3)
        ingest_pdf(event.src_path)


def start_invoice_watcher() -> Observer:
    folder = Path(settings.invoice_folder)
    folder.mkdir(parents=True, exist_ok=True)
    scan_existing_invoices()

    observer = Observer()
    observer.schedule(_InvoiceHandler(), str(folder), recursive=False)
    observer.start()
    logger.info("Fatura klasörü izleniyor: %s", folder.resolve())
    return observer

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
from app.services.pdf_compress import compress_pdf
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
    """EvoBulut sayılarını okur; Türkçe biçim de gelebiliyor.

    `float("0,00")` hata verip None döndürüyordu ve `Kalan` alanı bu biçimde
    geldiğinde fatura HİÇBİR ZAMAN ödendi sayılmıyordu - tahsil edilmiş
    faturaların uygulamada ödenmemiş görünmesinin sebebi buydu.

    Ayrım virgüle bakılarak yapılıyor: virgül varsa ondalık ayracı odur ve
    noktalar binlik ayracıdır ("1.234,56" → 1234.56). Virgül yoksa değer
    olduğu gibi okunur, yani "1234.56" bozulmaz.
    """
    if value in (None, ""):
        return None
    text = str(value).strip()
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    try:
        return float(text)
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
        compress_pdf(dest_path)
        return dest_path, os.path.basename(dest_path)
    except Exception:
        logger.exception("EvoBulut fatura %s için PDF indirilemedi", evobulut_id)
        return None


def _refresh_existing(invoice: Invoice, item: dict, amount: float | None) -> bool:
    """EvoBulut'ta sonradan değişen alanları mevcut faturaya işler.

    Bu olmadan senkronizasyon yalnızca YENİ fatura oluşturuyordu ve fatura bir
    kez aktarıldıktan sonra bir daha güncellenmiyordu. Sonucu: EvoBulut'ta
    tahsil edilen bir fatura uygulamada sonsuza kadar "ödenmemiş" görünüyordu
    ve vade uyarıları da gönderilmeye devam ediyordu (canlıda bildirildi).

    Ödeme durumunda kural tek yönlü: EvoBulut bir faturayı **ödendi yapabilir,
    ödenmemiş yapamaz**. Çünkü kullanıcı parayı aldığında uygulamadan elle
    "ödendi" işaretleyebiliyor; EvoBulut'a işlenmesi gün alabilir ve saatlik
    senkronizasyon bu işareti geri alsaydı yönetici aynı faturayı tekrar tekrar
    işaretlemek zorunda kalırdı.

    Diğer alanlar yalnızca BOŞSA doldurulur - elle yapılmış düzeltmelerin
    üzerine yazmamak için. Fatura numarası özellikle önemli: e-fatura
    gönderilene kadar EvoBulut "GÖNDERİLMEDİ" döndüğü için ilk aktarımda boş
    kalıyor, numara sonradan geliyor.
    """
    changed = False

    kalan = _parse_float(item.get("Kalan"))
    if amount and amount > 0 and kalan == 0 and invoice.status != InvoiceStatus.PAID:
        invoice.status = InvoiceStatus.PAID
        changed = True

    for field, value in (
        ("invoice_number", _invoice_number(item)),
        ("invoice_date", _parse_date(item.get("G.a_tarih"))),
        ("due_date", _parse_date(item.get("G.a_vtarih"))),
        ("amount", amount),
        ("counterparty", _counterparty(item)),
    ):
        if value is not None and getattr(invoice, field) is None:
            setattr(invoice, field, value)
            changed = True

    return changed


def sync_invoices_from_evobulut() -> dict:
    db = SessionLocal()
    created = 0
    updated = 0
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

            amount = _parse_float(item.get("G.a_tutar"))

            exists = db.query(Invoice).filter(Invoice.evobulut_id == evobulut_id).first()
            if exists:
                if _refresh_existing(exists, item, amount):
                    updated += 1
                else:
                    skipped += 1
                continue

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

    logger.info(
        "EvoBulut senkronizasyonu: %d yeni, %d güncellendi, %d değişmedi", created, updated, skipped
    )
    return {"ok": True, "created": created, "updated": updated, "skipped": skipped, "errors": errors}


def start_evobulut_sync_scheduler() -> BackgroundScheduler | None:
    if not settings.evobulut_username or not settings.evobulut_password:
        logger.info("EVOBULUT_USERNAME/PASSWORD ayarlanmamış, EvoBulut senkronizasyonu devre dışı")
        return None
    scheduler = BackgroundScheduler(timezone="Europe/Istanbul")
    scheduler.add_job(sync_invoices_from_evobulut, "interval", hours=1, next_run_time=datetime.now())
    scheduler.start()
    logger.info("EvoBulut senkronizasyon zamanlayıcısı başlatıldı (saatte bir çalışır)")
    return scheduler

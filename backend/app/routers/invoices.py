import os
from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.deps import get_current_user, require_admin
from app.models import Invoice, InvoiceStatus, Notification, User
from app.schemas import InvoiceOut, InvoiceUpdate
from app.services.invoice_watcher import ingest_pdf, scan_existing_invoices
from app.utils import safe_pdf_filename, unique_destination

router = APIRouter(prefix="/invoices", tags=["invoices"])
settings = get_settings()


def _with_days(invoice: Invoice) -> InvoiceOut:
    out = InvoiceOut.model_validate(invoice)
    if invoice.due_date:
        out.days_to_due = (invoice.due_date - date.today()).days
    return out


@router.get("", response_model=list[InvoiceOut])
def list_invoices(
    upcoming_only: bool = False,
    overdue_only: bool = False,
    q: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    query = db.query(Invoice)
    if q:
        like = f"%{q}%"
        query = query.filter(
            (Invoice.invoice_number.ilike(like)) | (Invoice.counterparty.ilike(like))
        )
    invoices = query.order_by(Invoice.invoice_number.is_(None), Invoice.invoice_number.desc()).all()

    today = date.today()
    if upcoming_only:
        invoices = [
            i for i in invoices if i.due_date and i.due_date >= today and i.status != InvoiceStatus.PAID
        ]
        invoices.sort(key=lambda i: i.due_date)
    if overdue_only:
        invoices = [
            i for i in invoices if i.due_date and i.due_date < today and i.status != InvoiceStatus.PAID
        ]
        invoices.sort(key=lambda i: i.due_date)

    return [_with_days(i) for i in invoices]


@router.post("/rescan")
def rescan_invoice_folder(_: User = Depends(require_admin)):
    scan_existing_invoices()
    return {"ok": True}


@router.get("/evobulut-diagnostics")
def evobulut_diagnostics(_: User = Depends(require_admin)):
    """EvoBulut bağlantısını test eder: giriş yapıp birkaç satış faturası
    çekmeyi dener, gerçek hatayı (varsa) döner."""
    from app.services.evobulut import EvoBulutError, fetch_sales_invoices

    try:
        items = fetch_sales_invoices()
        return {
            "ok": True,
            "message": f"EvoBulut'a başarıyla bağlanıldı, {len(items)} satış faturası bulundu.",
            "sample": items[0] if items else None,
        }
    except EvoBulutError as e:
        return {"ok": False, "message": str(e)}
    except Exception as e:
        return {"ok": False, "message": f"{type(e).__name__}: {e}"}


@router.get("/evobulut-diagnostics/pdf/{evobulut_id}")
def evobulut_pdf_diagnostics(evobulut_id: str, _: User = Depends(require_admin)):
    """Belirli bir EvoBulut fatura ID'si için PDF indirme URL'sini ve
    dosyanın gerçekten indirilip indirilemediğini test eder."""
    from app.services.evobulut import EvoBulutError, download_pdf_bytes, fetch_invoice_pdf_url

    try:
        url = fetch_invoice_pdf_url(evobulut_id)
        if not url:
            return {"ok": False, "message": "PDF URL'si dönmedi"}
        content = download_pdf_bytes(url)
        return {"ok": True, "url": url, "pdf_bytes": len(content), "starts_with_pdf_header": content[:4] == b"%PDF"}
    except EvoBulutError as e:
        return {"ok": False, "message": str(e)}
    except Exception as e:
        return {"ok": False, "message": f"{type(e).__name__}: {e}"}


@router.post("/evobulut-sync")
def evobulut_sync(_: User = Depends(require_admin)):
    from app.services.evobulut_sync import sync_invoices_from_evobulut

    return sync_invoices_from_evobulut()


MAX_UPLOAD_BYTES = 20 * 1024 * 1024


async def _save_and_ingest(file: UploadFile, db: Session) -> Invoice:
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail=f"'{file.filename}': sadece PDF dosyası yükleyebilirsiniz")

    folder = settings.invoice_folder
    os.makedirs(folder, exist_ok=True)
    dest_path = unique_destination(folder, safe_pdf_filename(file.filename))

    size = 0
    with open(dest_path, "wb") as out:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                out.close()
                os.remove(dest_path)
                raise HTTPException(status_code=400, detail=f"'{file.filename}': dosya çok büyük (maksimum 20 MB)")
            out.write(chunk)

    ingest_pdf(dest_path)

    invoice = db.query(Invoice).filter(Invoice.source_filename == os.path.basename(dest_path)).first()
    if not invoice:
        raise HTTPException(status_code=500, detail=f"'{file.filename}': fatura işlenemedi")
    return invoice


@router.post("/upload", response_model=InvoiceOut)
async def upload_invoice(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Fatura klasörüne fiziksel erişimi olmayan (örn. bulutta barındırılan)
    kurulumlarda, faturayı doğrudan uygulamadan yükleyip otomatik okumayı
    tetiklemek için kullanılır."""
    invoice = await _save_and_ingest(file, db)
    return _with_days(invoice)


@router.post("/bulk-upload")
async def bulk_upload_invoices(
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Birden fazla fatura PDF'ini tek seferde yükler (örn. /docs üzerinden
    'Try it out' ile birden fazla dosya seçilerek). Her dosya ayrı ayrı
    işlenir; biri başarısız olursa diğerleri etkilenmez."""
    created = 0
    errors = []
    for file in files:
        try:
            invoice = await _save_and_ingest(file, db)
            created += 1
            if invoice.status == InvoiceStatus.NEEDS_REVIEW:
                errors.append({"file": file.filename, "message": "Yüklendi ama bazı alanlar okunamadı, kontrol edin"})
        except HTTPException as e:
            errors.append({"file": file.filename, "message": e.detail})
    return {"created": created, "errors": errors}


@router.get("/{invoice_id}", response_model=InvoiceOut)
def get_invoice(invoice_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Fatura bulunamadı")
    return _with_days(invoice)


@router.patch("/{invoice_id}", response_model=InvoiceOut)
def update_invoice(invoice_id: int, payload: InvoiceUpdate, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Fatura bulunamadı")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(invoice, key, value)
    db.commit()
    db.refresh(invoice)
    return _with_days(invoice)


@router.delete("/{invoice_id}", status_code=204)
def delete_invoice(invoice_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Fatura bulunamadı")
    db.query(Notification).filter(Notification.invoice_id == invoice_id).delete()
    if invoice.file_path and os.path.exists(invoice.file_path):
        os.remove(invoice.file_path)
    db.delete(invoice)
    db.commit()


@router.get("/{invoice_id}/pdf")
def download_invoice_pdf(invoice_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    invoice = db.get(Invoice, invoice_id)
    if not invoice or not os.path.exists(invoice.file_path):
        raise HTTPException(status_code=404, detail="Fatura PDF bulunamadı")
    return FileResponse(invoice.file_path, media_type="application/pdf", filename=invoice.source_filename)

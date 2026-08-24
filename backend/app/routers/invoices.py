import os
from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.deps import get_current_user, require_admin
from app.models import Invoice, InvoiceStatus, Notification, NotificationRead, User
from app.schemas import InvoiceOut, InvoiceUpdate
from app.services.excel import build_workbook
from app.services.invoice_watcher import ingest_pdf, scan_existing_invoices
from app.utils import safe_pdf_filename, unique_destination
from app.services import audit, pdf_compress

router = APIRouter(prefix="/invoices", tags=["invoices"])
settings = get_settings()


def _with_days(invoice: Invoice) -> InvoiceOut:
    out = InvoiceOut.model_validate(invoice)
    if invoice.due_date:
        out.days_to_due = (invoice.due_date - date.today()).days
    return out


def _filtered_invoices(
    db: Session,
    upcoming_only: bool,
    overdue_only: bool,
    q: str | None,
    paid_only: bool = False,
) -> list[Invoice]:
    query = db.query(Invoice)
    if q:
        like = f"%{q}%"
        query = query.filter(
            (Invoice.invoice_number.ilike(like)) | (Invoice.counterparty.ilike(like))
        )
    invoices = query.order_by(Invoice.invoice_number.is_(None), Invoice.invoice_number.desc()).all()

    today = date.today()
    # Ödenmiş faturalar vade sekmelerinde görünmez: artık yapılacak bir iş değil.
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
    if paid_only:
        invoices = [i for i in invoices if i.status == InvoiceStatus.PAID]

    return invoices


@router.get("", response_model=list[InvoiceOut])
def list_invoices(
    upcoming_only: bool = False,
    overdue_only: bool = False,
    q: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return [_with_days(i) for i in _filtered_invoices(db, upcoming_only, overdue_only, q)]


INVOICE_STATUS_LABELS = {
    InvoiceStatus.PARSED: "Okundu",
    InvoiceStatus.NEEDS_REVIEW: "Kontrol Gerekli",
    InvoiceStatus.PAID: "Ödendi",
    InvoiceStatus.OVERDUE: "Vadesi Geçti",
    InvoiceStatus.UPCOMING: "Yaklaşıyor",
    InvoiceStatus.OPEN: "Açık",
}

EXPORT_COLUMNS = [
    "Fatura No",
    "Firma",
    "Fatura Tarihi",
    "Vade Tarihi",
    "Kalan Gün",
    "Tutar",
    "Para Birimi",
    "Durum",
    "Kaynak Dosya",
]


@router.get("/export")
def export_invoices(
    upcoming_only: bool = False,
    overdue_only: bool = False,
    paid_only: bool = False,
    q: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    invoices = _filtered_invoices(db, upcoming_only, overdue_only, q, paid_only)
    today = date.today()

    rows = [
        [
            i.invoice_number or "",
            i.counterparty or "",
            i.invoice_date.strftime("%d.%m.%Y") if i.invoice_date else "",
            i.due_date.strftime("%d.%m.%Y") if i.due_date else "",
            (i.due_date - today).days if i.due_date else "",
            i.amount if i.amount is not None else "",
            i.currency,
            INVOICE_STATUS_LABELS.get(i.status, i.status.value),
            i.source_filename,
        ]
        for i in invoices
    ]

    buffer = build_workbook("Faturalar", EXPORT_COLUMNS, rows)
    filename = f"fatura-raporu-{today.isoformat()}.xlsx"
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/rescan")
def rescan_invoice_folder(_: User = Depends(require_admin)):
    scan_existing_invoices()
    return {"ok": True}


@router.post("/compress-existing")
def compress_existing_invoice_pdfs(_: User = Depends(require_admin)):
    """Küçültme eklenmeden önce inmiş fatura PDF'lerini toplu küçültür.

    Yeni faturalar zaten küçültülüyor; bu uç birikmiş dosyalar için, elle
    çalıştırılır. Kazancın büyüğü taranmış faturalardan gelir - metin tabanlı
    e-faturalarda kazanç eşiğin altında kalır ve dosyaya dokunulmaz, o yüzden
    `islenen_pdf` toplam dosya sayısından küçük çıkabilir.
    """
    total_before = total_after = processed = seen = 0
    # evobulut/ alt klasörü de dahil: oradaki PDF'ler de yedeğe giriyor.
    for root, _dirs, files in os.walk(settings.invoice_folder):
        for name in files:
            if not name.lower().endswith(".pdf"):
                continue
            seen += 1
            result = pdf_compress.compress_pdf(os.path.join(root, name))
            total_before += result["before"]
            total_after += result["after"]
            processed += result["compressed"]

    return {
        "taranan_pdf": seen,
        "islenen_pdf": processed,
        "onceki_toplam_mb": round(total_before / 1024 / 1024, 2),
        "sonraki_toplam_mb": round(total_after / 1024 / 1024, 2),
        "kazanilan_mb": round((total_before - total_after) / 1024 / 1024, 2),
    }


# Ödeme durumuyla ilgili olabilecek alanlar. Tek tek bakmak yerine hepsini
# birden döndürüyoruz: "ödedim ama görünmüyor" denilen bir faturada EvoBulut'un
# hangi alanı ne yazdığını görmeden tahmin yürütmek anlamsız.
PAYMENT_FIELDS = ("G.a_tutar", "Kalan", "Kapatilan", "G.a_mn_kapat", "Dovizli_kalan_tutar")


@router.get("/evobulut-diagnostics")
def evobulut_diagnostics(fatura_no: str | None = None, _: User = Depends(require_admin)):
    """EvoBulut bağlantısını sınar ve ödeme tespitinin ne gördüğünü döner.

    `fatura_no` verilirse tüm sayfalarda o fatura aranır ve ham kaydı olduğu
    gibi döndürülür - "bu faturayı ödedim ama ödenmemiş görünüyor" denildiğinde
    EvoBulut'un o fatura için ne bildirdiğini görmenin tek yolu.
    """
    from app.services.evobulut import EvoBulutError, fetch_all_sales_invoices, fetch_sales_invoices

    from app.services.evobulut_sync import _parse_float

    try:
        if fatura_no:
            wanted = fatura_no.strip().lower()
            match = next(
                (
                    i for i in fetch_all_sales_invoices()
                    if (i.get("G.a_sbelge_seri_no") or "").strip().lower() == wanted
                ),
                None,
            )
            if match is None:
                return {"ok": False, "message": f"'{fatura_no}' EvoBulut'ta bulunamadı"}
            amount = _parse_float(match.get("G.a_tutar"))
            kalan = _parse_float(match.get("Kalan"))
            return {
                "ok": True,
                "fatura_no": fatura_no,
                "odeme_alanlari": {k: match.get(k) for k in PAYMENT_FIELDS},
                "odendi_sayilir": bool(amount and amount > 0 and kalan == 0),
                "ham_kayit": match,
            }

        items = fetch_sales_invoices()
        # Ödeme tespitinin neden tutmadığını görmek için: ham "Kalan" değeri,
        # bizim onu nasıl okuduğumuz ve verdiğimiz karar yan yana. Biçim
        # beklediğimizden farklıysa (ör. birim içeren "0,00 TL") burada
        # `kalan_okunan: null` olarak görünür.
        payment_rows = []
        for item in items[:10]:
            amount = _parse_float(item.get("G.a_tutar"))
            kalan = _parse_float(item.get("Kalan"))
            payment_rows.append(
                {
                    "fatura_no": item.get("G.a_sbelge_seri_no"),
                    "tutar_ham": item.get("G.a_tutar"),
                    "tutar_okunan": amount,
                    "kalan_ham": item.get("Kalan"),
                    "kalan_okunan": kalan,
                    "odendi_sayilir": bool(amount and amount > 0 and kalan == 0),
                }
            )

        return {
            "ok": True,
            "message": f"EvoBulut'a başarıyla bağlanıldı, {len(items)} satış faturası bulundu.",
            "odeme_tespiti": payment_rows,
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
def delete_invoice(invoice_id: int, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    invoice = db.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Fatura bulunamadı")
    audit.record(
        db, user, "delete", "invoice", invoice_id,
        f"Fatura silindi: {invoice.invoice_number or invoice.source_filename}"
        f" ({invoice.counterparty or 'firma bilinmiyor'}, {invoice.amount or 0} {invoice.currency})",
    )
    notification_ids = [
        n_id for (n_id,) in db.query(Notification.id).filter(Notification.invoice_id == invoice_id)
    ]
    if notification_ids:
        db.query(NotificationRead).filter(NotificationRead.notification_id.in_(notification_ids)).delete(
            synchronize_session=False
        )
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

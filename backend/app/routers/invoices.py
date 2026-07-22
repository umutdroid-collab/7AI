import os
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, require_admin
from app.models import Invoice, User
from app.schemas import InvoiceOut, InvoiceUpdate
from app.services.invoice_watcher import scan_existing_invoices

router = APIRouter(prefix="/invoices", tags=["invoices"])


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
    invoices = query.order_by(Invoice.due_date.is_(None), Invoice.due_date).all()

    today = date.today()
    if upcoming_only:
        invoices = [i for i in invoices if i.due_date and i.due_date >= today]
    if overdue_only:
        invoices = [i for i in invoices if i.due_date and i.due_date < today]

    return [_with_days(i) for i in invoices]


@router.post("/rescan")
def rescan_invoice_folder(_: User = Depends(require_admin)):
    scan_existing_invoices()
    return {"ok": True}


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


@router.get("/{invoice_id}/pdf")
def download_invoice_pdf(invoice_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    invoice = db.get(Invoice, invoice_id)
    if not invoice or not os.path.exists(invoice.file_path):
        raise HTTPException(status_code=404, detail="Fatura PDF bulunamadı")
    return FileResponse(invoice.file_path, media_type="application/pdf", filename=invoice.source_filename)

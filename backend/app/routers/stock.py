from datetime import date, datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.database import get_db
from app.deps import get_current_user, require_admin
from app.models import (
    MovementType,
    Notification,
    Product,
    StockItem,
    StockItemStatus,
    StockMovement,
    User,
)
from app.schemas import (
    StockItemCreate,
    StockItemOut,
    StockMovementOut,
    StockTransferRequest,
)
from app.services.bulk_import import CsvFormatError, import_stock_csv
from app.services.excel import build_workbook
from app.services import audit

router = APIRouter(prefix="/stock", tags=["stock"])
settings = get_settings()


def _with_expiry(item: StockItem) -> StockItemOut:
    out = StockItemOut.model_validate(item)
    out.days_to_expiry = (item.skt - date.today()).days
    return out


def _filtered_stock_query(
    db: Session,
    hospital_id: int | None,
    carried_by_user_id: int | None,
    q: str | None,
    expiring_within_days: int | None,
    include_used: bool,
    status: StockItemStatus | None,
):
    """Konsinye stok listesi. hospital_id verilmezse depodaki + tüm hastanelerdeki ürünler döner.
    q: ref no / ÜBB no / lot no / seri no üzerinde arama yapar (hangi hastanede ne var, karışıklığı çözer).
    carried_by_user_id: bir çalışanın o an aracında/üzerinde taşıdığı ürünleri filtrelemek için.
    status: belirli bir durumu filtrelemek için (örn. "used" ile Kullanım sekmesi hangi hastanede
    kullanıldığını gösterir). Verilirse include_used göz ardı edilir.
    """
    query = db.query(StockItem).join(Product).options(
        joinedload(StockItem.product),
        joinedload(StockItem.hospital),
        joinedload(StockItem.carried_by),
    )
    if hospital_id is not None:
        query = query.filter(StockItem.hospital_id == hospital_id)
    if carried_by_user_id is not None:
        query = query.filter(StockItem.carried_by_user_id == carried_by_user_id)
    if status is not None:
        query = query.filter(StockItem.status == status)
    elif not include_used:
        query = query.filter(StockItem.status != StockItemStatus.USED)
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                Product.reference_no.ilike(like),
                Product.ubb_no.ilike(like),
                Product.name.ilike(like),
                StockItem.lot_no.ilike(like),
                StockItem.serial_no.ilike(like),
            )
        )
    if expiring_within_days is not None:
        cutoff = date.today()
        from datetime import timedelta

        query = query.filter(StockItem.skt <= cutoff + timedelta(days=expiring_within_days))

    if status == StockItemStatus.USED:
        return query.order_by(StockItem.updated_at.desc())
    return query.order_by(StockItem.skt)


@router.get("", response_model=list[StockItemOut])
def list_stock(
    hospital_id: int | None = None,
    carried_by_user_id: int | None = None,
    q: str | None = None,
    expiring_within_days: int | None = None,
    include_used: bool = False,
    status: StockItemStatus | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    items = _filtered_stock_query(
        db, hospital_id, carried_by_user_id, q, expiring_within_days, include_used, status
    ).all()
    return [_with_expiry(i) for i in items]


STATUS_LABELS = {
    StockItemStatus.IN_STOCK: "Depoda",
    StockItemStatus.AT_HOSPITAL: "Hastanede",
    StockItemStatus.IN_VEHICLE: "Araçta",
    StockItemStatus.USED: "Kullanıldı",
    StockItemStatus.RETURNED: "İade Edildi",
    StockItemStatus.EXPIRED: "SKT Geçti",
}

EXPORT_COLUMNS = [
    "Ürün",
    "Ref No",
    "ÜBB No",
    "SUT Kodu",
    "Lot No",
    "Seri No",
    "SKT",
    "Kalan Gün",
    "Miktar",
    "Durum",
    "Konum",
    "Taşıyan",
    "Kayıt Tarihi",
]


@router.get("/export")
def export_stock(
    hospital_id: int | None = None,
    carried_by_user_id: int | None = None,
    q: str | None = None,
    expiring_within_days: int | None = None,
    include_used: bool = False,
    status: StockItemStatus | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    items = _filtered_stock_query(
        db, hospital_id, carried_by_user_id, q, expiring_within_days, include_used, status
    ).all()

    rows = []
    for item in items:
        location = item.hospital.name if item.hospital else (f"{item.carried_by.full_name} (araçta)" if item.carried_by else "Depo")
        rows.append([
            item.product.name,
            item.product.reference_no,
            item.product.ubb_no or "",
            item.product.sut_kodu or "",
            item.lot_no,
            item.serial_no or "",
            item.skt.strftime("%d.%m.%Y"),
            (item.skt - date.today()).days,
            item.quantity,
            STATUS_LABELS.get(item.status, item.status.value),
            location,
            item.carried_by.full_name if item.carried_by else "",
            item.created_at.strftime("%d.%m.%Y"),
        ])

    buffer = build_workbook("Stok", EXPORT_COLUMNS, rows)

    filename = f"stok-raporu-{date.today().isoformat()}.xlsx"
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{stock_item_id}", response_model=StockItemOut)
def get_stock_item(stock_item_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    item = db.get(StockItem, stock_item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Stok kaydı bulunamadı")
    return _with_expiry(item)


@router.get("/{stock_item_id}/history", response_model=list[StockMovementOut])
def get_stock_history(stock_item_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    item = db.get(StockItem, stock_item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Stok kaydı bulunamadı")
    return item.movements


@router.post("", response_model=StockItemOut)
def create_stock_item(payload: StockItemCreate, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    product = db.get(Product, payload.product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Ürün bulunamadı")

    status_ = StockItemStatus.AT_HOSPITAL if payload.hospital_id else StockItemStatus.IN_STOCK
    item = StockItem(
        product_id=payload.product_id,
        lot_no=payload.lot_no,
        serial_no=payload.serial_no,
        skt=payload.skt,
        quantity=payload.quantity,
        hospital_id=payload.hospital_id,
        status=status_,
    )
    db.add(item)
    db.flush()

    movement = StockMovement(
        stock_item_id=item.id,
        movement_type=MovementType.DISPATCH if payload.hospital_id else MovementType.ADJUSTMENT,
        from_hospital_id=None,
        to_hospital_id=payload.hospital_id,
        moved_by_user_id=user.id,
        note="İlk stok girişi",
    )
    db.add(movement)
    db.commit()
    db.refresh(item)
    return _with_expiry(item)


@router.post("/bulk-upload")
async def bulk_upload_stock(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    """CSV sütunları: reference_no, lot_no, skt (zorunlu), serial_no, quantity,
    hospital_name (opsiyonel; boşsa depo). reference_no daha önce eklenmiş bir
    ürünle, hospital_name daha önce eklenmiş bir hastaneyle eşleşmelidir."""
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Sadece CSV dosyası yükleyebilirsiniz")
    content = await file.read()
    try:
        result = import_stock_csv(content, db, user)
    except CsvFormatError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"created": result.created, "skipped": result.skipped, "errors": result.errors}


@router.post("/{stock_item_id}/transfer", response_model=StockItemOut)
def transfer_stock_item(
    stock_item_id: int,
    payload: StockTransferRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Bir ürünü mevcut hastaneden başka bir hastaneye taşır, bir çalışanın aracına
    aldırır ya da depoya iade eder. Bu, çalışanların hangi ürünün hangi hastanede /
    kimin aracında olduğunu güncel tutmasını sağlayan tek yoldur.
    """
    item = db.get(StockItem, stock_item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Stok kaydı bulunamadı")

    was_used = item.status == StockItemStatus.USED
    from_hospital_id = item.hospital_id
    to_vehicle_user_id: int | None = None

    if payload.to_vehicle:
        movement_type = MovementType.VEHICLE_PICKUP
        item.status = StockItemStatus.IN_VEHICLE
        item.hospital_id = None
        item.carried_by_user_id = user.id
        to_vehicle_user_id = user.id
    elif payload.to_hospital_id is None:
        movement_type = MovementType.RETURN
        item.status = StockItemStatus.IN_STOCK
        item.hospital_id = None
        item.carried_by_user_id = None
    elif from_hospital_id is None:
        movement_type = MovementType.DISPATCH
        item.status = StockItemStatus.AT_HOSPITAL
        item.hospital_id = payload.to_hospital_id
        item.carried_by_user_id = None
    else:
        movement_type = MovementType.TRANSFER
        item.status = StockItemStatus.AT_HOSPITAL
        item.hospital_id = payload.to_hospital_id
        item.carried_by_user_id = None

    note = payload.note
    if was_used:
        # Yanlışlıkla "kullanıldı" işaretlenmiş bir ürünün geri alınması: gerçek bir
        # fiziksel taşıma değil, durum düzeltmesi olarak kaydedilir.
        movement_type = MovementType.ADJUSTMENT
        note = note or "Kullanım işareti geri alındı"

    item.updated_at = datetime.utcnow()

    movement = StockMovement(
        stock_item_id=item.id,
        movement_type=movement_type,
        from_hospital_id=from_hospital_id,
        to_hospital_id=item.hospital_id,
        to_vehicle_user_id=to_vehicle_user_id,
        moved_by_user_id=user.id,
        note=note,
    )
    db.add(movement)
    db.commit()
    db.refresh(item)
    return _with_expiry(item)


@router.post("/{stock_item_id}/mark-used", response_model=StockItemOut)
def mark_used(stock_item_id: int, note: str | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    item = db.get(StockItem, stock_item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Stok kaydı bulunamadı")
    item.status = StockItemStatus.USED
    item.updated_at = datetime.utcnow()
    db.add(StockMovement(
        stock_item_id=item.id,
        movement_type=MovementType.USE,
        from_hospital_id=item.hospital_id,
        to_hospital_id=item.hospital_id,
        moved_by_user_id=user.id,
        note=note,
    ))
    db.commit()
    db.refresh(item)
    return _with_expiry(item)


@router.delete("/{stock_item_id}")
def delete_stock_item(stock_item_id: int, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    item = db.get(StockItem, stock_item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Stok kaydı bulunamadı")
    audit.record(
        db, user, "delete", "stock_item", stock_item_id,
        f"Stok kaydı silindi: {item.product.name} (Lot {item.lot_no}, Seri {item.serial_no or '-'})",
    )
    db.delete(item)
    db.commit()
    return {"ok": True}

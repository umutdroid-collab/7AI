from datetime import date, datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import or_
from sqlalchemy.orm import Session

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
from app.services.bulk_import import import_stock_csv

router = APIRouter(prefix="/stock", tags=["stock"])
settings = get_settings()


def _with_expiry(item: StockItem) -> StockItemOut:
    out = StockItemOut.model_validate(item)
    out.days_to_expiry = (item.skt - date.today()).days
    return out


@router.get("", response_model=list[StockItemOut])
def list_stock(
    hospital_id: int | None = None,
    q: str | None = None,
    expiring_within_days: int | None = None,
    include_used: bool = False,
    status: StockItemStatus | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Konsinye stok listesi. hospital_id verilmezse depodaki + tüm hastanelerdeki ürünler döner.
    q: ref no / ÜBB no / lot no / seri no üzerinde arama yapar (hangi hastanede ne var, karışıklığı çözer).
    status: belirli bir durumu filtrelemek için (örn. "used" ile Kullanım sekmesi hangi hastanede
    kullanıldığını gösterir). Verilirse include_used göz ardı edilir.
    """
    query = db.query(StockItem).join(Product)
    if hospital_id is not None:
        query = query.filter(StockItem.hospital_id == hospital_id)
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
        items = query.order_by(StockItem.updated_at.desc()).all()
    else:
        items = query.order_by(StockItem.skt).all()
    return [_with_expiry(i) for i in items]


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
def create_stock_item(payload: StockItemCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
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
    result = import_stock_csv(content, db, user)
    return {"created": result.created, "skipped": result.skipped, "errors": result.errors}


@router.post("/{stock_item_id}/transfer", response_model=StockItemOut)
def transfer_stock_item(
    stock_item_id: int,
    payload: StockTransferRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Bir ürünü mevcut hastaneden başka bir hastaneye taşır ya da depoya iade eder.
    Bu, çalışanların hangi ürünün hangi hastanede olduğunu güncel tutmasını sağlayan tek yoldur.
    """
    item = db.get(StockItem, stock_item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Stok kaydı bulunamadı")

    was_used = item.status == StockItemStatus.USED
    from_hospital_id = item.hospital_id

    if payload.to_hospital_id is None:
        movement_type = MovementType.RETURN
        item.status = StockItemStatus.IN_STOCK
    elif from_hospital_id is None:
        movement_type = MovementType.DISPATCH
        item.status = StockItemStatus.AT_HOSPITAL
    else:
        movement_type = MovementType.TRANSFER
        item.status = StockItemStatus.AT_HOSPITAL

    note = payload.note
    if was_used:
        # Yanlışlıkla "kullanıldı" işaretlenmiş bir ürünün geri alınması: gerçek bir
        # fiziksel taşıma değil, durum düzeltmesi olarak kaydedilir.
        movement_type = MovementType.ADJUSTMENT
        note = note or "Kullanım işareti geri alındı"

    item.hospital_id = payload.to_hospital_id
    item.updated_at = datetime.utcnow()

    movement = StockMovement(
        stock_item_id=item.id,
        movement_type=movement_type,
        from_hospital_id=from_hospital_id,
        to_hospital_id=payload.to_hospital_id,
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
def delete_stock_item(stock_item_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    item = db.get(StockItem, stock_item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Stok kaydı bulunamadı")
    db.delete(item)
    db.commit()
    return {"ok": True}

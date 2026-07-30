from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.deps import get_current_user, require_admin
from app.models import MovementType, Product, SalesTarget, StockItem, StockMovement, User, UserRole
from app.schemas import (
    SalesTargetContributor,
    SalesTargetCreate,
    SalesTargetOut,
    SalesTargetProgressAdjust,
    SalesTargetUpdate,
)

router = APIRouter(prefix="/targets", tags=["sales_targets"])


def _with_progress(target: SalesTarget, db: Session) -> SalesTargetOut:
    out = SalesTargetOut.model_validate(target)

    # Ürüne bağlı olmayan (manuel) hedeflerde stok hareketlerinden hesaplanacak
    # bir şey yok; ilerleme tamamen elle girilen değerden gelir.
    if target.product_id is None:
        out.progress = target.manual_progress
        return out

    query = (
        db.query(StockMovement, StockItem)
        .join(StockItem, StockMovement.stock_item_id == StockItem.id)
        .filter(
            StockMovement.movement_type == MovementType.USE,
            StockItem.product_id == target.product_id,
            StockMovement.moved_at >= datetime.combine(target.period_start, datetime.min.time()),
            StockMovement.moved_at <= datetime.combine(target.period_end, datetime.max.time()),
        )
    )
    if target.assigned_user_id is not None:
        query = query.filter(StockMovement.moved_by_user_id == target.assigned_user_id)

    rows = query.all()

    contributor_totals: dict[int, int] = {}
    for movement, stock_item in rows:
        if movement.moved_by_user_id is None:
            continue
        contributor_totals[movement.moved_by_user_id] = (
            contributor_totals.get(movement.moved_by_user_id, 0) + stock_item.quantity
        )

    # Otomatik hesaplanan kullanım + yöneticinin elle girdiği düzeltme.
    out.progress = sum(contributor_totals.values()) + target.manual_progress

    if target.assigned_user_id is None and contributor_totals:
        users = db.query(User).filter(User.id.in_(contributor_totals.keys())).all()
        users_by_id = {u.id: u for u in users}
        out.contributors = [
            SalesTargetContributor(user_id=uid, full_name=users_by_id[uid].full_name, quantity=qty)
            for uid, qty in contributor_totals.items()
            if uid in users_by_id
        ]
        out.contributors.sort(key=lambda c: c.quantity, reverse=True)

    return out


@router.post("", response_model=SalesTargetOut)
def create_target(
    payload: SalesTargetCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    if payload.period_end < payload.period_start:
        raise HTTPException(status_code=400, detail="Bitiş tarihi başlangıç tarihinden önce olamaz")

    if payload.product_id is not None and not db.get(Product, payload.product_id):
        raise HTTPException(status_code=404, detail="Ürün bulunamadı")

    target = SalesTarget(**payload.model_dump(), created_by_user_id=user.id)
    db.add(target)
    db.commit()
    db.refresh(target)
    return _with_progress(target, db)


@router.get("", response_model=list[SalesTargetOut])
def list_targets(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    query = db.query(SalesTarget).options(joinedload(SalesTarget.product), joinedload(SalesTarget.assigned_user))
    if user.role != UserRole.ADMIN:
        query = query.filter(
            (SalesTarget.assigned_user_id == user.id) | (SalesTarget.assigned_user_id.is_(None))
        )
    targets = query.order_by(SalesTarget.period_start.desc()).all()
    return [_with_progress(t, db) for t in targets]


@router.delete("/{target_id}")
def delete_target(target_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    target = db.get(SalesTarget, target_id)
    if not target:
        raise HTTPException(status_code=404, detail="Hedef bulunamadı")
    db.delete(target)
    db.commit()
    return {"ok": True}


def _get_target_or_404(target_id: int, db: Session) -> SalesTarget:
    target = db.get(SalesTarget, target_id)
    if not target:
        raise HTTPException(status_code=404, detail="Hedef bulunamadı")
    return target


@router.patch("/{target_id}", response_model=SalesTargetOut)
def update_target(
    target_id: int,
    payload: SalesTargetUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    target = _get_target_or_404(target_id, db)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(target, key, value)
    if target.period_end < target.period_start:
        raise HTTPException(status_code=400, detail="Bitiş tarihi başlangıç tarihinden önce olamaz")
    db.commit()
    db.refresh(target)
    return _with_progress(target, db)


@router.post("/{target_id}/progress", response_model=SalesTargetOut)
def adjust_progress(
    target_id: int,
    payload: SalesTargetProgressAdjust,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Yöneticinin hedef ilerlemesini elle artırıp azaltması (+/-) içindir.

    Ürüne bağlı hedeflerde stok hareketlerinden gelen otomatik sayının
    ÜSTÜNE eklenir; sisteme girilmemiş bir kullanımı elle işlemek için.
    """
    target = _get_target_or_404(target_id, db)

    # Toplam ilerlemenin negatife düşmesi anlamsız; eksiye götürecek bir
    # azaltma sıfırda durdurulur. (Manuel hedeflerde otomatik kısım 0 olduğu
    # için aynı hesap ikisinde de çalışır.)
    current_total = _with_progress(target, db).progress
    applied_delta = payload.delta if current_total + payload.delta >= 0 else -current_total
    target.manual_progress += applied_delta

    db.commit()
    db.refresh(target)
    return _with_progress(target, db)

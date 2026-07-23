from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, require_admin
from app.models import MovementType, SalesTarget, StockItem, StockMovement, User, UserRole
from app.schemas import SalesTargetContributor, SalesTargetCreate, SalesTargetOut

router = APIRouter(prefix="/targets", tags=["sales_targets"])


def _with_progress(target: SalesTarget, db: Session) -> SalesTargetOut:
    out = SalesTargetOut.model_validate(target)

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

    out.progress = sum(contributor_totals.values())

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

    target = SalesTarget(**payload.model_dump(), created_by_user_id=user.id)
    db.add(target)
    db.commit()
    db.refresh(target)
    return _with_progress(target, db)


@router.get("", response_model=list[SalesTargetOut])
def list_targets(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    query = db.query(SalesTarget)
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

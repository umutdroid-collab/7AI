from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import Notification, NotificationRead, User
from app.schemas import NotificationOut

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _read_ids_for(user: User, db: Session) -> set[int]:
    rows = db.query(NotificationRead.notification_id).filter(NotificationRead.user_id == user.id).all()
    return {r[0] for r in rows}


def _to_out(notification: Notification, read_ids: set[int]) -> NotificationOut:
    out = NotificationOut.model_validate(notification)
    out.is_read = notification.id in read_ids
    return out


@router.get("", response_model=list[NotificationOut])
def list_notifications(
    unread_only: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    read_ids = _read_ids_for(user, db)
    query = db.query(Notification)
    if unread_only and read_ids:
        query = query.filter(Notification.id.notin_(read_ids))
    notifications = query.order_by(Notification.created_at.desc()).limit(200).all()
    return [_to_out(n, read_ids) for n in notifications]


@router.post("/{notification_id}/read", response_model=NotificationOut)
def mark_read(notification_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    notification = db.get(Notification, notification_id)
    if not notification:
        raise HTTPException(status_code=404, detail="Bildirim bulunamadı")
    already = (
        db.query(NotificationRead)
        .filter(NotificationRead.notification_id == notification_id, NotificationRead.user_id == user.id)
        .first()
    )
    if not already:
        db.add(NotificationRead(notification_id=notification_id, user_id=user.id))
        db.commit()
    return _to_out(notification, {notification_id})


@router.post("/read-all")
def mark_all_read(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    read_ids = _read_ids_for(user, db)
    unread = db.query(Notification.id)
    if read_ids:
        unread = unread.filter(Notification.id.notin_(read_ids))
    for (notification_id,) in unread.all():
        db.add(NotificationRead(notification_id=notification_id, user_id=user.id))
    db.commit()
    return {"ok": True}

"""Yöneticinin takip notları ("Hatırlatıcılar").

Çalışanların check-in yorumları arasında dikkat çeken bir şey, listede aşağı
kaydıkça kayboluyordu. Buradaki notlar o yorumdan bağımsız bir kayda dönüşür,
tarihi geldiğinde günlük özet e-postasında hatırlatılır ve toplantıda
konuşulduktan sonra tamamlandı olarak işaretlenir.
"""

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.deps import require_admin
from app.models import CheckIn, FollowUp, User
from app.schemas import FollowUpCheckInSummary, FollowUpCreate, FollowUpOut, FollowUpUpdate
from app.services import audit

router = APIRouter(prefix="/follow-ups", tags=["follow-ups"])


def _to_out(follow_up: FollowUp) -> FollowUpOut:
    """Alanlar tek tek verilir: check-in özeti ORM'deki CheckIn'den farklı bir
    şekle sahip (hastane ve çalışan adı düzleştirilmiş), o yüzden otomatik
    eşleme kullanılamıyor."""
    checkin = follow_up.checkin
    return FollowUpOut(
        id=follow_up.id,
        note=follow_up.note,
        remind_on=follow_up.remind_on,
        is_done=follow_up.is_done,
        done_at=follow_up.done_at,
        created_at=follow_up.created_at,
        about_user=follow_up.about_user,
        created_by=follow_up.created_by,
        days_until_due=(follow_up.remind_on - date.today()).days,
        checkin=(
            FollowUpCheckInSummary(
                id=checkin.id,
                hospital_name=checkin.hospital.name,
                user_name=checkin.user.full_name,
                comment=checkin.comment,
                checked_in_at=checkin.checked_in_at,
            )
            if checkin
            else None
        ),
    )


def _base_query(db: Session):
    return db.query(FollowUp).options(
        joinedload(FollowUp.about_user),
        joinedload(FollowUp.created_by),
        joinedload(FollowUp.checkin).joinedload(CheckIn.hospital),
        joinedload(FollowUp.checkin).joinedload(CheckIn.user),
    )


@router.get("", response_model=list[FollowUpOut])
def list_follow_ups(
    include_done: bool = False,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Varsayılan olarak yalnızca açık notlar; tarihi en yakın olan en üstte.

    Tamamlananlar listeyi doldurmasın diye gizli, ama geçmişe bakılabilsin
    diye silinmiyor.
    """
    query = _base_query(db)
    if not include_done:
        query = query.filter(FollowUp.is_done.is_(False))
    items = query.order_by(FollowUp.is_done, FollowUp.remind_on).all()
    return [_to_out(item) for item in items]


@router.post("", response_model=FollowUpOut)
def create_follow_up(
    payload: FollowUpCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    if payload.checkin_id is not None and not db.get(CheckIn, payload.checkin_id):
        raise HTTPException(status_code=404, detail="Giriş kaydı bulunamadı")

    follow_up = FollowUp(
        note=payload.note.strip(),
        checkin_id=payload.checkin_id,
        about_user_id=payload.about_user_id,
        remind_on=payload.remind_on,
        created_by_user_id=user.id,
    )
    db.add(follow_up)
    db.commit()
    db.refresh(follow_up)
    return _to_out(follow_up)


@router.patch("/{follow_up_id}", response_model=FollowUpOut)
def update_follow_up(
    follow_up_id: int,
    payload: FollowUpUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    follow_up = db.get(FollowUp, follow_up_id)
    if not follow_up:
        raise HTTPException(status_code=404, detail="Hatırlatıcı bulunamadı")

    if payload.note is not None:
        if not payload.note.strip():
            raise HTTPException(status_code=400, detail="Not boş olamaz")
        follow_up.note = payload.note.strip()
    if payload.remind_on is not None:
        follow_up.remind_on = payload.remind_on
    if payload.about_user_id is not None:
        follow_up.about_user_id = payload.about_user_id
    if payload.is_done is not None:
        follow_up.is_done = payload.is_done
        # Tamamlanma anı kaydedilir; geri açılırsa temizlenir ki eski tarih
        # yanlış bilgi vermesin.
        follow_up.done_at = datetime.utcnow() if payload.is_done else None

    db.commit()
    db.refresh(follow_up)
    return _to_out(follow_up)


@router.delete("/{follow_up_id}")
def delete_follow_up(
    follow_up_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    follow_up = db.get(FollowUp, follow_up_id)
    if not follow_up:
        raise HTTPException(status_code=404, detail="Hatırlatıcı bulunamadı")

    audit.record(
        db, user, "delete", "follow_up", follow_up_id, f"Hatırlatıcı silindi: {follow_up.note[:80]}"
    )
    db.delete(follow_up)
    db.commit()
    return {"ok": True}

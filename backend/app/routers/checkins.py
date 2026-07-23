import os
from datetime import date, datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.deps import get_current_user, require_admin
from app.models import CheckIn, Hospital, User, UserRole
from app.schemas import CheckInOut, CheckInUpdate
from app.utils import safe_image_filename, unique_destination

router = APIRouter(prefix="/checkins", tags=["checkins"])
settings = get_settings()

MAX_UPLOAD_BYTES = 15 * 1024 * 1024


@router.post("", response_model=CheckInOut)
async def create_checkin(
    hospital_id: int = Form(...),
    comment: str | None = Form(None),
    photo: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Çalışan hastaneye vardığında fotoğraf çekip giriş yapar; kayıt anı
    'işe başlama saati' olarak, hospital_id ise 'nerede oldukları' olarak
    kullanılır."""
    hospital = db.get(Hospital, hospital_id)
    if not hospital:
        raise HTTPException(status_code=404, detail="Hastane bulunamadı")

    folder = settings.checkin_photos_folder
    os.makedirs(folder, exist_ok=True)
    dest_path = unique_destination(folder, safe_image_filename(photo.filename or "checkin.jpg"))

    size = 0
    with open(dest_path, "wb") as out:
        while chunk := await photo.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                out.close()
                os.remove(dest_path)
                raise HTTPException(status_code=400, detail="Fotoğraf çok büyük (maksimum 15 MB)")
            out.write(chunk)

    checkin = CheckIn(
        user_id=user.id,
        hospital_id=hospital_id,
        photo_path=dest_path,
        comment=comment or None,
    )
    db.add(checkin)
    db.commit()
    db.refresh(checkin)
    return checkin


@router.get("", response_model=list[CheckInOut])
def list_checkins(
    user_id: int | None = None,
    hospital_id: int | None = None,
    day: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(CheckIn)

    if current_user.role != UserRole.ADMIN:
        query = query.filter(CheckIn.user_id == current_user.id)
    elif user_id is not None:
        query = query.filter(CheckIn.user_id == user_id)

    if hospital_id is not None:
        query = query.filter(CheckIn.hospital_id == hospital_id)
    if day is not None:
        start = datetime.combine(day, datetime.min.time())
        end = datetime.combine(day, datetime.max.time())
        query = query.filter(CheckIn.checked_in_at >= start, CheckIn.checked_in_at <= end)

    return query.order_by(CheckIn.checked_in_at.desc()).limit(300).all()


def _get_checkin_or_404(checkin_id: int, db: Session) -> CheckIn:
    checkin = db.get(CheckIn, checkin_id)
    if not checkin:
        raise HTTPException(status_code=404, detail="Giriş kaydı bulunamadı")
    return checkin


def _ensure_can_view(checkin: CheckIn, user: User) -> None:
    if user.role != UserRole.ADMIN and checkin.user_id != user.id:
        raise HTTPException(status_code=403, detail="Bu kayda erişim yetkiniz yok")


@router.get("/{checkin_id}/photo")
def get_checkin_photo(checkin_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    checkin = _get_checkin_or_404(checkin_id, db)
    _ensure_can_view(checkin, user)
    if not os.path.exists(checkin.photo_path):
        raise HTTPException(status_code=404, detail="Fotoğraf bulunamadı")
    return FileResponse(checkin.photo_path)


@router.patch("/{checkin_id}", response_model=CheckInOut)
def update_checkin(
    checkin_id: int,
    payload: CheckInUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    checkin = _get_checkin_or_404(checkin_id, db)
    _ensure_can_view(checkin, user)
    checkin.comment = payload.comment
    db.commit()
    db.refresh(checkin)
    return checkin


@router.delete("/{checkin_id}")
def delete_checkin(checkin_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    checkin = _get_checkin_or_404(checkin_id, db)
    if os.path.exists(checkin.photo_path):
        os.remove(checkin.photo_path)
    db.delete(checkin)
    db.commit()
    return {"ok": True}

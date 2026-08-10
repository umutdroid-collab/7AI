import os
from datetime import date, datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.database import get_db
from app.deps import get_current_user, require_admin
from app.models import CheckIn, Hospital, User, UserRole
from app.schemas import CheckInOut, CheckInUpdate
from app.utils import safe_image_filename, unique_destination
from app.services import audit, images
from app.services.excel import build_workbook

router = APIRouter(prefix="/checkins", tags=["checkins"])
settings = get_settings()

MAX_UPLOAD_BYTES = 15 * 1024 * 1024


@router.post("", response_model=CheckInOut)
async def create_checkin(
    hospital_id: int = Form(...),
    comment: str | None = Form(None),
    latitude: float | None = Form(None),
    longitude: float | None = Form(None),
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

    # Diske kalıcı olarak yazılan hâli küçültülmüş olan; ham dosya saklanmıyor.
    images.compress_checkin_photo(dest_path)

    checkin = CheckIn(
        user_id=user.id,
        hospital_id=hospital_id,
        photo_path=dest_path,
        comment=comment or None,
        latitude=latitude,
        longitude=longitude,
    )
    db.add(checkin)
    db.commit()
    db.refresh(checkin)
    return checkin


def _filtered_checkin_query(
    db: Session,
    current_user: User,
    user_id: int | None,
    hospital_id: int | None,
    day: date | None,
    start_date: date | None,
    end_date: date | None,
):
    """Liste ve Excel dışa aktarımı aynı filtreleri kullansın diye ortak.

    Yetki filtresi burada: çalışan yalnızca kendi girişlerini görür, yönetici
    hepsini. Bu kural iki yerde ayrı ayrı yazılsaydı birinde unutulabilirdi.
    """
    query = db.query(CheckIn).options(joinedload(CheckIn.user), joinedload(CheckIn.hospital))

    if current_user.role != UserRole.ADMIN:
        query = query.filter(CheckIn.user_id == current_user.id)
    elif user_id is not None:
        query = query.filter(CheckIn.user_id == user_id)

    if hospital_id is not None:
        query = query.filter(CheckIn.hospital_id == hospital_id)
    if day is not None:
        query = query.filter(
            CheckIn.checked_in_at >= datetime.combine(day, datetime.min.time()),
            CheckIn.checked_in_at <= datetime.combine(day, datetime.max.time()),
        )
    if start_date is not None:
        query = query.filter(CheckIn.checked_in_at >= datetime.combine(start_date, datetime.min.time()))
    if end_date is not None:
        query = query.filter(CheckIn.checked_in_at <= datetime.combine(end_date, datetime.max.time()))

    return query.order_by(CheckIn.checked_in_at.desc())


@router.get("", response_model=list[CheckInOut])
def list_checkins(
    user_id: int | None = None,
    hospital_id: int | None = None,
    day: date | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        _filtered_checkin_query(db, current_user, user_id, hospital_id, day, start_date, end_date)
        .limit(300)
        .all()
    )


EXPORT_COLUMNS = ["Tarih", "Saat", "Çalışan", "Hastane", "Şehir", "Not", "Konum"]


@router.get("/export")
def export_checkins(
    user_id: int | None = None,
    hospital_id: int | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Ziyaret raporunu Excel olarak verir. Fotoğraf yok - rapor belirli bir
    aralıkta kimin nereye gittiğini ve ne not düştüğünü görmek için."""
    checkins = _filtered_checkin_query(
        db, current_user, user_id, hospital_id, None, start_date, end_date
    ).all()

    rows = [
        [
            c.checked_in_at.strftime("%d.%m.%Y"),
            c.checked_in_at.strftime("%H:%M"),
            c.user.full_name,
            c.hospital.name,
            c.hospital.city or "",
            c.comment or "",
            f"{c.latitude:.5f}, {c.longitude:.5f}" if c.latitude is not None and c.longitude is not None else "",
        ]
        for c in checkins
    ]

    buffer = build_workbook("Ziyaretler", EXPORT_COLUMNS, rows)
    filename = f"ziyaret-raporu-{date.today().isoformat()}.xlsx"
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _get_checkin_or_404(checkin_id: int, db: Session) -> CheckIn:
    checkin = db.get(CheckIn, checkin_id)
    if not checkin:
        raise HTTPException(status_code=404, detail="Giriş kaydı bulunamadı")
    return checkin


def _ensure_can_view(checkin: CheckIn, user: User) -> None:
    if user.role != UserRole.ADMIN and checkin.user_id != user.id:
        raise HTTPException(status_code=403, detail="Bu kayda erişim yetkiniz yok")


@router.get("/{checkin_id}/photo")
def get_checkin_photo(
    checkin_id: int,
    boyut: str = "tam",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """boyut=onizleme küçük önizlemeyi, boyut=tam (varsayılan) tam boyu döner.

    Liste kartlarında fotoğraf 64 pikselde gösteriliyor; oraya tam boy dosyayı
    indirmek mobil veride gereksiz yük. Büyütmek için tam boy istenir.
    """
    checkin = _get_checkin_or_404(checkin_id, db)
    _ensure_can_view(checkin, user)
    if not os.path.exists(checkin.photo_path):
        raise HTTPException(status_code=404, detail="Fotoğraf bulunamadı")

    path = images.ensure_thumbnail(checkin.photo_path) if boyut == "onizleme" else checkin.photo_path
    return FileResponse(path)


@router.post("/compress-existing")
def compress_existing_photos(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    """Sıkıştırma eklenmeden önce yüklenmiş fotoğrafları toplu küçültür.

    Yeni yüklemeler zaten küçültülüyor; bu uç yalnızca birikmiş eski
    fotoğrafların kapladığı yeri geri kazanmak için, elle çalıştırılır.
    """
    total_before = total_after = processed = 0
    for checkin in db.query(CheckIn).all():
        if not os.path.exists(checkin.photo_path):
            continue
        result = images.compress_checkin_photo(checkin.photo_path)
        total_before += result["before"]
        total_after += result["after"]
        processed += result["compressed"]

    return {
        "islenen_fotograf": processed,
        "onceki_toplam_mb": round(total_before / 1024 / 1024, 2),
        "sonraki_toplam_mb": round(total_after / 1024 / 1024, 2),
        "kazanilan_mb": round((total_before - total_after) / 1024 / 1024, 2),
    }


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
def delete_checkin(checkin_id: int, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    checkin = _get_checkin_or_404(checkin_id, db)
    audit.record(
        db, user, "delete", "checkin", checkin_id,
        f"Giriş kaydı silindi: {checkin.user.full_name} - {checkin.hospital.name}"
        f" ({checkin.checked_in_at:%d.%m.%Y %H:%M})",
    )
    images.remove_photo_files(checkin.photo_path)
    db.delete(checkin)
    db.commit()
    return {"ok": True}

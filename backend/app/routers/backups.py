from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_admin
from app.services import audit, offsite_backup
from app.models import User
from app.services.backup import backup_path, create_backup, list_backups, restore_backup

router = APIRouter(prefix="/backups", tags=["backups"])


@router.get("")
def get_backups(_: User = Depends(require_admin)):
    return list_backups()


@router.post("/run")
def run_backup(_: User = Depends(require_admin)):
    filename = create_backup()
    return {"ok": True, "filename": filename}


@router.get("/offsite/status")
def offsite_status(_: User = Depends(require_admin)):
    """Dış depo bağlantısını sınar ve gerçek hatayı döner - normal akışta
    yükleme hataları yutuluyor, buradan görünür."""
    return offsite_backup.status()


@router.get("/offsite")
def offsite_list(_: User = Depends(require_admin)):
    """Dış depodaki kopyalar. Yerel liste kaybolduğunda elde ne olduğunu
    görmenin tek yolu."""
    try:
        return offsite_backup.list_remote()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Dış depoya erişilemedi: {e}")


@router.post("/{filename}/offsite-upload")
def upload_existing_to_offsite(filename: str, _: User = Depends(require_admin)):
    """Mevcut bir yerel yedeği elle dış depoya kopyalar - dış depo sonradan
    yapılandırıldığında birikmiş yedekleri göndermek için."""
    try:
        path = backup_path(filename)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Yedek bulunamadı")
    return offsite_backup.upload(str(path))


@router.get("/{filename}/download")
def download_backup(filename: str, _: User = Depends(require_admin)):
    try:
        path = backup_path(filename)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Yedek bulunamadı")
    return FileResponse(path, media_type="application/zip", filename=filename)


@router.post("/{filename}/restore")
def restore(
    filename: str,
    confirm: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
):
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Bu işlem mevcut verilerin üzerine yazar. Onaylamak için ?confirm=true ekleyin.",
        )
    try:
        restore_backup(filename)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Yedek bulunamadı")
    # Geri yükleme veritabanının üzerine yazdığı için günlük kaydı SONRA ve
    # ayrı bir oturumda yazılır - önce yazılsaydı geri yüklenen dosyayla
    # birlikte kaybolurdu.
    from app.database import SessionLocal

    fresh = SessionLocal()
    try:
        audit.record(fresh, user, "restore", "backup", filename, f"Sistem '{filename}' yedeğinden geri yüklendi")
        fresh.commit()
    finally:
        fresh.close()
    return {"ok": True}


@router.delete("/{filename}")
def delete_backup(filename: str, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    try:
        path = backup_path(filename)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Yedek bulunamadı")
    path.unlink()
    audit.record(db, user, "delete", "backup", filename, f"Yedek silindi: {filename}")
    db.commit()
    return {"ok": True}

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.deps import require_admin
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


@router.get("/{filename}/download")
def download_backup(filename: str, _: User = Depends(require_admin)):
    try:
        path = backup_path(filename)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Yedek bulunamadı")
    return FileResponse(path, media_type="application/zip", filename=filename)


@router.post("/{filename}/restore")
def restore(filename: str, confirm: bool = False, _: User = Depends(require_admin)):
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Bu işlem mevcut verilerin üzerine yazar. Onaylamak için ?confirm=true ekleyin.",
        )
    try:
        restore_backup(filename)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Yedek bulunamadı")
    return {"ok": True}


@router.delete("/{filename}")
def delete_backup(filename: str, _: User = Depends(require_admin)):
    try:
        path = backup_path(filename)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Yedek bulunamadı")
    path.unlink()
    return {"ok": True}

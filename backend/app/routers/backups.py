import os
import zipfile

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_admin
from app.services import audit, offsite_backup
from app.models import User
from app.services.backup import backup_path, create_backup, list_backups, restore_backup, size_report

router = APIRouter(prefix="/backups", tags=["backups"])


@router.get("")
def get_backups(_: User = Depends(require_admin)):
    return list_backups()


@router.post("/run")
def run_backup(_: User = Depends(require_admin)):
    filename = create_backup()
    return {"ok": True, "filename": filename}


@router.get("/size-report")
def get_size_report(_: User = Depends(require_admin)):
    """Yedeğin içinde neyin ne kadar yer kapladığı. Sıkıştırma kararını
    tahminle değil bu çıktıya bakarak verin."""
    return size_report()


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


@router.post("/offsite/{filename}/pull")
def pull_from_offsite(filename: str, _: User = Depends(require_admin)):
    """Dış depodaki bir yedeği yerel klasöre indirir; sonra normal
    `POST /backups/{dosya}/restore` ile geri yüklenebilir.

    Felaket senaryosunun eksik halkası buydu: Railway diski gittiğinde elde
    yalnızca R2 kopyası kalıyor ve geri yükleme onu göremiyordu.
    """
    from app.config import get_settings

    try:
        path = offsite_backup.download(filename, get_settings().backup_dir)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Dış depodan indirilemedi: {e}")
    return {"ok": True, "filename": os.path.basename(path), "size_bytes": os.path.getsize(path)}


@router.post("/upload")
async def upload_backup(file: UploadFile = File(...), _: User = Depends(require_admin)):
    """Elde tutulan bir .zip yedeği sisteme geri koyar.

    Dış depo da kaybedilmişse (ya da hiç kurulmamışsa) elle indirilmiş bir
    yedekten dönmenin tek yolu. Yükleme geri yüklemez; ardından
    `POST /backups/{dosya}/restore?confirm=true` çağrılmalı.
    """
    filename = os.path.basename(file.filename or "")
    if not filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Yalnızca .zip yedek dosyası yüklenebilir")

    from app.config import get_settings

    folder = get_settings().backup_dir
    os.makedirs(folder, exist_ok=True)
    dest = os.path.join(folder, filename)
    with open(dest, "wb") as out:
        while chunk := await file.read(1024 * 1024):
            out.write(chunk)

    # Bozuk/yanlış dosya geri yükleme anında değil, şimdi fark edilmeli.
    if not zipfile.is_zipfile(dest):
        os.remove(dest)
        raise HTTPException(status_code=400, detail="Dosya geçerli bir .zip arşivi değil")

    return {"ok": True, "filename": filename, "size_bytes": os.path.getsize(dest)}


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

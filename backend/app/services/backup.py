"""Railway'in Hobby planında otomatik Volume yedeklemesi olmadığı için,
veritabanı + yüklenen dosyaları (fatura PDF'leri, klinik çalışmalar, check-in
fotoğrafları, vektör indeksi) düzenli aralıklarla tek bir .zip'e paketleyip
saklayan basit bir yedekleme sistemi."""

import logging
import os
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import get_settings

logger = logging.getLogger("backup")
settings = get_settings()

FOLDER_ARCNAMES = [
    ("invoice_folder", "invoices"),
    ("clinical_docs_folder", "clinical_docs"),
    ("checkin_photos_folder", "checkins"),
    ("vector_db_dir", "vectorstore"),
]


def _sqlite_path() -> str | None:
    url = settings.database_url
    if url.startswith("sqlite:///"):
        return url[len("sqlite:///"):]
    return None


def _backup_dir() -> Path:
    d = Path(settings.backup_dir)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _snapshot_sqlite(sqlite_path: str, dest_path: str) -> None:
    """Canlı veritabanının tutarlı bir kopyasını alır. Dosyayı doğrudan
    kopyalamak, tam o anda bir yazma işlemi varsa bozuk bir yedek üretebilir;
    SQLite'ın kendi backup API'si bunu güvenli şekilde yapar."""
    src = sqlite3.connect(sqlite_path)
    try:
        dst = sqlite3.connect(dest_path)
        try:
            with dst:
                src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()


def create_backup() -> str:
    """Mevcut DB + veri klasörlerinden bir .zip yedek oluşturur, dosya adını döner."""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    filename = f"yedek-{timestamp}.zip"
    dest = _backup_dir() / filename

    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        sqlite_path = _sqlite_path()
        if sqlite_path and os.path.exists(sqlite_path):
            with tempfile.TemporaryDirectory() as tmp:
                snapshot_path = os.path.join(tmp, "app.db")
                _snapshot_sqlite(sqlite_path, snapshot_path)
                zf.write(snapshot_path, arcname="app.db")

        for setting_name, arc_prefix in FOLDER_ARCNAMES:
            folder = getattr(settings, setting_name)
            if not os.path.isdir(folder):
                continue
            for root, _dirs, files in os.walk(folder):
                for name in files:
                    full = os.path.join(root, name)
                    rel = os.path.relpath(full, folder)
                    zf.write(full, arcname=os.path.join(arc_prefix, rel))

    logger.info("Yedek oluşturuldu: %s", dest)
    _prune_old_backups()
    return filename


def _prune_old_backups() -> None:
    files = sorted(_backup_dir().glob("yedek-*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in files[settings.backup_keep_count:]:
        old.unlink()
        logger.info("Eski yedek silindi: %s", old.name)


def list_backups() -> list[dict]:
    files = sorted(_backup_dir().glob("yedek-*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
    return [
        {
            "filename": p.name,
            "size_bytes": p.stat().st_size,
            "created_at": datetime.fromtimestamp(p.stat().st_mtime).isoformat(),
        }
        for p in files
    ]


def backup_path(filename: str) -> Path:
    """Yol geçişi (path traversal) girişimlerine karşı sadece dosya adını kullanır."""
    safe_name = os.path.basename(filename)
    path = _backup_dir() / safe_name
    if not path.is_file() or path.suffix != ".zip":
        raise FileNotFoundError(filename)
    return path


def restore_backup(filename: str) -> None:
    """Verilen yedekten DB + veri klasörlerini geri yükler. Geri dönülemez bir
    işlem olduğu için önce mevcut durumun bir güvenlik yedeğini alır."""
    source = backup_path(filename)

    with tempfile.TemporaryDirectory() as tmp:
        # Önce geri yüklenecek yedeği aç (kaynağı diskten okumayı burada bitir),
        # SONRA mevcut durumun güvenlik yedeğini al - aksi halde aynı saniye
        # içindeki iki yedek aynı dosya adını alıp kaynağın üzerine yazabilir.
        with zipfile.ZipFile(source) as zf:
            zf.extractall(tmp)

        create_backup()  # geri yüklemeden hemen önceki durumu da sakla (yanlış yedek seçilirse geri dönebilmek için)

        from app.database import engine

        engine.dispose()

        sqlite_path = _sqlite_path()
        extracted_db = os.path.join(tmp, "app.db")
        if sqlite_path and os.path.exists(extracted_db):
            os.makedirs(os.path.dirname(sqlite_path) or ".", exist_ok=True)
            shutil.copy2(extracted_db, sqlite_path)

        for setting_name, arc_prefix in FOLDER_ARCNAMES:
            extracted_folder = os.path.join(tmp, arc_prefix)
            if not os.path.isdir(extracted_folder):
                continue
            target_folder = getattr(settings, setting_name)
            if os.path.isdir(target_folder):
                shutil.rmtree(target_folder)
            shutil.copytree(extracted_folder, target_folder)

    # Vektör dizini de az önce diskte değiştirildi; açık olan Chroma istemcisi
    # artık silinmiş bir dizine bakıyor - bırakılmazsa klinik asistan sunucu
    # yeniden başlatılana kadar çalışmaz.
    from app.services.vector_store import reset_client

    reset_client()

    logger.warning("Sistem şu yedekten geri yüklendi: %s", filename)


def start_backup_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="Europe/Istanbul")
    scheduler.add_job(create_backup, "interval", weeks=1)
    scheduler.start()
    logger.info("Yedekleme zamanlayıcısı başlatıldı (haftada bir çalışır)")
    return scheduler

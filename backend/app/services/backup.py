"""Railway'in Hobby planında otomatik Volume yedeklemesi olmadığı için,
veritabanı + yüklenen dosyaları (fatura PDF'leri, klinik çalışmalar, check-in
fotoğrafları, vektör indeksi) düzenli aralıklarla tek bir .zip'e paketleyip
saklayan basit bir yedekleme sistemi."""

import logging
import os
import shutil
import sqlite3
import tempfile
import time
import zipfile
from datetime import datetime, timedelta, timezone
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

    # Dış depo kopyası: yapılandırılmamışsa sessizce atlanır, yükleme
    # başarısız olursa da yerel yedek geçerli sayılır (upload hata yükseltmez).
    from app.services import offsite_backup

    offsite_backup.upload(str(dest))

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
            # Saat dilimi işaretiyle: işaretsiz gönderilirse tarayıcı yerel
            # saat sanıp yanlış saat gösteriyor (bkz. schemas.UtcDateTime).
            "created_at": datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc).isoformat(),
        }
        for p in files
    ]


def size_report() -> dict:
    """Yedeğe neyin ne kadar yer kapladığını gösterir.

    "Yedekler büyüdü" denildiğinde hangi klasörün baskın olduğunu tahmin
    etmeye gerek kalmasın diye: sıkıştırmayı doğru yere uygulamanın tek yolu
    önce ölçmek. Yerelde `backup_keep_count`, dış depoda `backup_s3_keep_count`
    kopya tutulduğu için tek dosyada kazanılan yer o sayılarla çarpılır.
    """
    folders = []
    biggest: list[tuple[int, str]] = []
    total = 0
    for setting_name, arc_prefix in FOLDER_ARCNAMES:
        folder = getattr(settings, setting_name)
        size = count = 0
        for root, _dirs, files in os.walk(folder):
            for name in files:
                full = os.path.join(root, name)
                try:
                    file_size = os.path.getsize(full)
                except OSError:
                    continue
                size += file_size
                count += 1
                biggest.append((file_size, os.path.join(arc_prefix, os.path.relpath(full, folder))))
        total += size
        folders.append({"klasor": arc_prefix, "dosya_sayisi": count, "mb": round(size / 1024 / 1024, 2)})

    # Klasör toplamı "nereye bakmalı"yı söyler ama "neyi silmeli"yi söylemez;
    # tek bir şişmiş dosya (ör. Chroma'nın WAL'ı) toplamı domine edebiliyor.
    biggest.sort(reverse=True)

    sqlite_path = _sqlite_path()
    db_bytes = os.path.getsize(sqlite_path) if sqlite_path and os.path.exists(sqlite_path) else 0
    total += db_bytes

    backups = list_backups()
    return {
        "veritabani_mb": round(db_bytes / 1024 / 1024, 2),
        "klasorler": sorted(folders, key=lambda f: f["mb"], reverse=True),
        "en_buyuk_dosyalar": [
            {"dosya": name, "mb": round(size / 1024 / 1024, 2)} for size, name in biggest[:12]
        ],
        "sikistirilmamis_toplam_mb": round(total / 1024 / 1024, 2),
        "son_yedek_mb": round(backups[0]["size_bytes"] / 1024 / 1024, 2) if backups else None,
        "yerel_yedek_sayisi": len(backups),
        "yerel_yedekler_toplam_mb": round(sum(b["size_bytes"] for b in backups) / 1024 / 1024, 2),
    }


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


BACKUP_INTERVAL_DAYS = 7
# Gecikmiş yedek açılışta hemen alınmaz: 200 MB'lık bir zip üretmek CPU ve
# disk yiyor, platformun açılış sağlık kontrolüne denk gelmesin.
CATCH_UP_DELAY_SECONDS = 120


def newest_backup_age_days() -> float | None:
    """En yeni yedeğin kaç gün önce alındığı; hiç yedek yoksa None."""
    files = sorted(_backup_dir().glob("yedek-*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        return None
    return (time.time() - files[0].stat().st_mtime) / 86400


def start_backup_scheduler() -> BackgroundScheduler:
    """Haftalık yedekleme.

    Eskiden `interval, weeks=1` kullanılıyordu ve bu, ilk çalışmayı açılıştan
    **bir hafta sonraya** koyuyordu. Railway her deploy'da süreci yeniden
    başlattığı için sayaç sürekli sıfırlanıyor ve haftada birden sık deploy
    edildiğinde yedek **hiç alınmıyordu** - canlıda doğrulandı (17.08.2026:
    `size-report` → `yerel_yedek_sayisi: 0`, dış depoya da kopyalanacak bir
    şey yoktu).

    Çözüm iki parçalı: sabit bir haftalık saat (deploy sayaca dokunmaz) ve
    açılışta diskteki en yeni yedeğe bakıp gecikmişse bir kerelik telafi
    çalışması. Telafinin ölçüsü diskteki dosya olduğu için süreç kaç kez
    yeniden başlarsa başlasın haftada bir yedekten fazlası alınmaz.
    """
    scheduler = BackgroundScheduler(timezone="Europe/Istanbul")
    scheduler.add_job(create_backup, "cron", day_of_week="sun", hour=3, minute=0, id="weekly-backup")

    age = newest_backup_age_days()
    if age is None or age >= BACKUP_INTERVAL_DAYS:
        # Saat dilimi bilinçli olmalı: zamanlayıcı Europe/Istanbul'da çalışıyor
        # ama container UTC, naive bir tarih 3 saat geçmişe düşüp işi tam
        # açılışta tetikliyordu.
        due_at = datetime.now(timezone.utc) + timedelta(seconds=CATCH_UP_DELAY_SECONDS)
        scheduler.add_job(create_backup, "date", run_date=due_at, id="catch-up-backup")
        logger.warning(
            "Gecikmiş yedek tespit edildi (en yeni yedek: %s), %s içinde bir kere alınacak",
            "yok" if age is None else f"{age:.1f} gün önce",
            f"{CATCH_UP_DELAY_SECONDS} sn",
        )

    scheduler.start()
    logger.info("Yedekleme zamanlayıcısı başlatıldı (her pazar 03:00)")
    return scheduler

"""Yedeklerin S3 uyumlu bir dış depoya kopyalanması.

Neden: `services/backup.py` haftalık .zip'i Railway diskine yazıyor ve orada
tek kopya kalıyor. Disk bozulursa ya da servis silinirse yedekler de gider -
yani yedeğin asıl koruması gereken senaryoda işe yaramaz.

Sağlayıcıdan bağımsız tutuldu: Cloudflare R2, Backblaze B2, AWS S3 ve
benzerleri aynı S3 API'sini konuşuyor, yalnızca endpoint/anahtar değişiyor.
Yapılandırılmamışsa tüm çağrılar sessizce "devre dışı" döner; yedekleme yine
yerelde çalışmaya devam eder.
"""

import logging
import os
from functools import lru_cache

from app.config import get_settings

logger = logging.getLogger("offsite_backup")
settings = get_settings()

PREFIX = "yedekler/"


def is_configured() -> bool:
    return all(
        [
            settings.backup_s3_endpoint,
            settings.backup_s3_bucket,
            settings.backup_s3_access_key,
            settings.backup_s3_secret_key,
        ]
    )


@lru_cache(maxsize=1)
def _client():
    import boto3

    return boto3.client(
        "s3",
        endpoint_url=settings.backup_s3_endpoint,
        aws_access_key_id=settings.backup_s3_access_key,
        aws_secret_access_key=settings.backup_s3_secret_key,
        region_name=settings.backup_s3_region,
    )


def upload(local_path: str) -> dict:
    """Bir yedeği dış depoya yükler ve eski kopyaları budar.

    Hata yükseltmez: dış kopya alınamadı diye yerel yedeklemenin başarısız
    sayılması yanlış olurdu - elde hâlâ çalışan bir yedek var.
    """
    if not is_configured():
        return {"ok": False, "reason": "yapilandirilmamis"}

    key = PREFIX + os.path.basename(local_path)
    try:
        _client().upload_file(local_path, settings.backup_s3_bucket, key)
        size = os.path.getsize(local_path)
        logger.info("Yedek dış depoya kopyalandı: %s (%.1f MB)", key, size / 1024 / 1024)
        pruned = prune()
        return {"ok": True, "key": key, "size_bytes": size, "silinen_eski": pruned}
    except Exception as e:
        logger.exception("Yedek dış depoya kopyalanamadı: %s", key)
        return {"ok": False, "reason": f"{type(e).__name__}: {e}"}


def list_remote() -> list[dict]:
    """Dış depodaki yedekleri yeniden eskiye sıralı döner."""
    if not is_configured():
        return []

    response = _client().list_objects_v2(Bucket=settings.backup_s3_bucket, Prefix=PREFIX)
    items = [
        {
            "filename": obj["Key"][len(PREFIX):],
            "size_bytes": obj["Size"],
            # S3 LastModified zaten saat dilimi bilgisi taşıyor.
            "created_at": obj["LastModified"].isoformat(),
        }
        for obj in response.get("Contents", [])
    ]
    return sorted(items, key=lambda i: i["created_at"], reverse=True)


def download(filename: str, dest_folder: str) -> str:
    """Dış depodaki bir yedeği yerel yedek klasörüne indirir, yolunu döner.

    Bu olmadan dış kopya, tasarlandığı senaryoda (Railway diski gitti) işe
    yaramıyordu: geri yükleme yalnızca yerel klasördeki dosyayı okuyor, dış
    depodan içeri bir yol yoktu. Zinciri kapatan halka bu.

    Yükleme/indirmenin aksine burada hata **yükseltilir**: kullanıcı bilinçli
    olarak bir geri yükleme başlatıyor, sessizce başarısız olması tehlikeli.
    """
    if not is_configured():
        raise RuntimeError("Dış depo yapılandırılmamış")

    # Yol geçişine karşı: uzaktan gelen ad da olsa yalnızca dosya adı kullanılır.
    safe_name = os.path.basename(filename)
    if not safe_name.endswith(".zip"):
        raise ValueError("Yalnızca .zip yedekleri indirilebilir")

    os.makedirs(dest_folder, exist_ok=True)
    dest_path = os.path.join(dest_folder, safe_name)
    _client().download_file(settings.backup_s3_bucket, PREFIX + safe_name, dest_path)
    logger.info("Yedek dış depodan indirildi: %s", safe_name)
    return dest_path


def prune() -> int:
    """Son `backup_s3_keep_count` kopyayı bırakır, kalanı siler.

    Depo sınırsız değil ve her yedek tüm yüklenen dosyaları içeriyor;
    budanmazsa ücretsiz kota kısa sürede dolar.
    """
    if not is_configured():
        return 0

    extras = list_remote()[settings.backup_s3_keep_count:]
    if not extras:
        return 0

    _client().delete_objects(
        Bucket=settings.backup_s3_bucket,
        Delete={"Objects": [{"Key": PREFIX + item["filename"]} for item in extras]},
    )
    logger.info("Dış depodan %d eski yedek silindi", len(extras))
    return len(extras)


def status() -> dict:
    """Teşhis için: yapılandırma var mı, depoya gerçekten erişilebiliyor mu."""
    if not is_configured():
        return {
            "yapilandirilmis": False,
            "mesaj": "BACKUP_S3_ENDPOINT, BACKUP_S3_BUCKET, BACKUP_S3_ACCESS_KEY ve "
            "BACKUP_S3_SECRET_KEY tanımlanmalı",
        }
    try:
        remote = list_remote()
        return {
            "yapilandirilmis": True,
            "erisim": True,
            "bucket": settings.backup_s3_bucket,
            "kopya_sayisi": len(remote),
            "toplam_mb": round(sum(i["size_bytes"] for i in remote) / 1024 / 1024, 2),
            "en_yeni": remote[0]["created_at"] if remote else None,
        }
    except Exception as e:
        # Yanlış anahtar, yanlış bucket adı, yanlış endpoint - hepsi burada
        # görünür; normal akışta bu hata yutuluyor.
        return {"yapilandirilmis": True, "erisim": False, "mesaj": f"{type(e).__name__}: {e}"}

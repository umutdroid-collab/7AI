"""Check-in fotoğraflarını sunucu tarafında küçültür.

Railway Hobby'de disk küçük ve yedeklenmiyor; telefondan gelen ham fotoğraf
3-5 MB olabiliyor ve günde onlarca check-in yapılıyor. Sıkıştırmayı istemciye
bırakmak yetmez: eski uygulama sürümleri, farklı tarayıcılar ve doğrudan API'ye
yapılan istekler yine ham dosya gönderir. Bu yüzden küçültme yükleme anında,
sunucuda ve şartsız yapılır.

Ayrıca listede 64 pikselde gösterilen fotoğraf için tam boy dosyayı indirmek
mobil veride pahalı; küçük bir önizleme dosyası da üretilir (asıl dosyanın
~%5'i kadar yer kaplar).
"""

import logging
import os

from PIL import Image, ImageOps

logger = logging.getLogger("images")

# Tam boy görüntüleme için: telefon ekranında 1280 piksel fazlasıyla yeterli,
# 12 MP ham fotoğrafın yanında ~20 kat küçük.
MAX_DIMENSION = 1280
JPEG_QUALITY = 72

# Liste önizlemesi için (kartlarda 64 pikselde gösteriliyor; ekran
# yoğunluğu için pay bırakıldı).
THUMB_DIMENSION = 240
THUMB_QUALITY = 60

THUMB_SUFFIX = "__onizleme.jpg"


def thumbnail_path(photo_path: str) -> str:
    base, _ext = os.path.splitext(photo_path)
    return base + THUMB_SUFFIX


def _prepare(image: Image.Image) -> Image.Image:
    """EXIF yönünü uygular ve JPEG'e yazılabilir bir moda çevirir.

    EXIF olmadan telefon fotoğrafları yan yatık görünür. JPEG şeffaflık
    desteklemediği için RGBA/P kipindeki görüntüler dönüştürülmeli.
    """
    image = ImageOps.exif_transpose(image)
    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")
    return image


def compress_checkin_photo(path: str) -> dict:
    """Fotoğrafı yerinde küçültür ve önizlemesini üretir.

    Sıkıştırma başarısız olursa (bozuk dosya, desteklenmeyen biçim) hata
    yükseltmez: check-in kaydının kendisi fotoğraf küçültülemedi diye
    kaybedilmemeli, dosya olduğu gibi bırakılır.
    """
    before = os.path.getsize(path)
    try:
        with Image.open(path) as raw:
            image = _prepare(raw)

            preview = image.copy()
            preview.thumbnail((THUMB_DIMENSION, THUMB_DIMENSION))
            preview.save(thumbnail_path(path), "JPEG", quality=THUMB_QUALITY, optimize=True)

            image.thumbnail((MAX_DIMENSION, MAX_DIMENSION))
            # EXIF taşınmaz: hem yer kaplar hem konum/cihaz bilgisi sızdırabilir.
            image.save(path, "JPEG", quality=JPEG_QUALITY, optimize=True)
    except Exception:
        logger.exception("Fotoğraf küçültülemedi, orijinali korunuyor: %s", path)
        return {"before": before, "after": before, "compressed": False}

    after = os.path.getsize(path)
    logger.info("Fotoğraf küçültüldü: %s (%d -> %d bayt)", os.path.basename(path), before, after)
    return {"before": before, "after": after, "compressed": True}


def ensure_thumbnail(photo_path: str) -> str:
    """Önizleme yoksa üretir, yolunu döner.

    Sıkıştırma eklenmeden önce yüklenmiş fotoğrafların önizlemesi yok; toplu
    bir dönüşüm beklemeden ilk görüntülemede üretilsin diye tembel çalışır.
    Üretilemezse tam boy dosyanın yolu dönerek görüntüleme yine de çalışır.
    """
    thumb = thumbnail_path(photo_path)
    if os.path.exists(thumb):
        return thumb
    try:
        with Image.open(photo_path) as raw:
            image = _prepare(raw)
            image.thumbnail((THUMB_DIMENSION, THUMB_DIMENSION))
            image.save(thumb, "JPEG", quality=THUMB_QUALITY, optimize=True)
        return thumb
    except Exception:
        logger.exception("Önizleme üretilemedi: %s", photo_path)
        return photo_path


def remove_photo_files(photo_path: str) -> None:
    """Fotoğrafı ve varsa önizlemesini siler."""
    for path in (photo_path, thumbnail_path(photo_path)):
        if os.path.exists(path):
            os.remove(path)

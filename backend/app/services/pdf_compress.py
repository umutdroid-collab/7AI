"""Fatura PDF'lerini sunucuda küçültür.

Check-in fotoğraflarıyla aynı gerekçe: Railway diski küçük ve her haftalık
yedek **tüm** yüklenen dosyaları içeriyor, yani bir fatura PDF'i yerelde 8,
dış depoda 12 kopya olarak duruyor. Tek dosyada kazanılan her megabayt
yirmiyle çarpılıyor.

Ama fotoğraftan farklı olarak PDF'te kazanç garanti değil:

- **Metin tabanlı e-fatura** (EvoBulut'tan gelenlerin tamamı böyle) zaten
  30-150 KB'tır ve içinde küçültülecek görüntü yoktur. Burada tek kazanç
  kayıpsız yeniden paketlemedir (nesne akışları + sıkıştırılmamış içerik
  akışlarının deflate'lenmesi) ve genelde küçüktür.
- **Taranmış fatura** (elle klasöre bırakılanlar) sayfa başına birkaç MB'lık
  görüntü taşır; asıl kazanç oradadır.

Bu yüzden küçültme koşulludur: sonuç en az %10 küçük değilse dosya olduğu
gibi bırakılır. Aksi halde her `rescan` çağrısında PDF'ler boşuna yeniden
yazılır ve zaten optimum olan dosyalar bozulma riskine sokulurdu.

Metin çıkarımı (`invoice_parser`) görüntülerden etkilenmez; sıkıştırma
okunan fatura alanlarını değiştirmez.
"""

import io
import logging
import os
import shutil
import tempfile

import pikepdf
from PIL import Image

logger = logging.getLogger("pdf_compress")

# Taranmış faturanın ekranda ve baskıda okunabilir kalması gereken çözünürlük.
# A4'ün uzun kenarı 1600 pikselde ~135 DPI eder; fatura satırları rahat okunur.
MAX_IMAGE_DIMENSION = 1600
JPEG_QUALITY = 70

# Logo/imza gibi küçük görüntüleri ellemek riske değmez, kazancı da yok.
MIN_IMAGE_BYTES = 40 * 1024

# Bu orandan az kazanç varsa orijinal korunur (bkz. modül açıklaması).
MIN_GAIN_RATIO = 0.10


def _recompress_image(stream) -> bool:
    """Gömülü bir görüntüyü küçültüp yerine yazar. Değiştirdiyse True döner."""
    try:
        raw_len = len(stream.read_raw_bytes())
    except Exception:
        return False
    if raw_len < MIN_IMAGE_BYTES:
        return False

    # Maske ve şeffaflık taşıyan görüntüler JPEG'e çevrilirse bozulur; taranmış
    # faturalarda bunlar zaten görülmez, atlamak en güvenlisi.
    if stream.get("/ImageMask") or stream.get("/SMask") or stream.get("/Mask"):
        return False

    try:
        image = pikepdf.PdfImage(stream).as_pil_image()
    except Exception:
        # Desteklenmeyen renk uzayı / bozuk akış: dokunma.
        return False

    if image.mode not in ("RGB", "L"):
        try:
            image = image.convert("RGB")
        except Exception:
            return False

    image.thumbnail((MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION))

    buffer = io.BytesIO()
    try:
        image.save(buffer, "JPEG", quality=JPEG_QUALITY, optimize=True)
    except Exception:
        return False
    data = buffer.getvalue()

    # Zaten iyi sıkıştırılmış bir görüntüyü daha büyük bir JPEG'le değiştirmek
    # ters teperdi.
    if len(data) >= raw_len:
        return False

    stream.write(data, filter=pikepdf.Name("/DCTDecode"))
    stream.Width, stream.Height = image.width, image.height
    stream.ColorSpace = pikepdf.Name("/DeviceGray" if image.mode == "L" else "/DeviceRGB")
    stream.BitsPerComponent = 8
    # Eski filtrenin çözme parametreleri yeni JPEG akışına uymaz.
    if "/DecodeParms" in stream:
        del stream["/DecodeParms"]
    if "/Decode" in stream:
        del stream["/Decode"]
    return True


def compress_invoice_pdf(path: str) -> dict:
    """PDF'i yerinde küçültür. Kazanç eşiğin altındaysa dosyaya dokunmaz.

    Hata yükseltmez: faturanın kendisi (ve okunan alanları) PDF küçültülemedi
    diye kaybedilmemeli, dosya olduğu gibi bırakılır.
    """
    before = os.path.getsize(path)
    tmp_path = None
    try:
        with pikepdf.open(path) as pdf:
            for page in pdf.pages:
                # get_images() form XObject'lerin içine de iner; bazı
                # entegratörler sayfanın tamamını tek bir XObject olarak
                # yerleştiriyor ve yüzeysel tarama görüntüyü hiç görmüyor.
                for stream in page.get_images().values():
                    _recompress_image(stream)

            # Görüntü olmasa bile kazanç bırakabilir: nesne akışları ve
            # sıkıştırılmamış içerik akışları burada toparlanır.
            fd, tmp_path = tempfile.mkstemp(suffix=".pdf", dir=os.path.dirname(path) or ".")
            os.close(fd)
            pdf.save(
                tmp_path,
                compress_streams=True,
                object_stream_mode=pikepdf.ObjectStreamMode.generate,
                recompress_flate=True,
            )

        after = os.path.getsize(tmp_path)
        if after > before * (1 - MIN_GAIN_RATIO):
            os.remove(tmp_path)
            return {"before": before, "after": before, "compressed": False}

        # Aynı dosya sistemi içinde: yerine koyma atomik olur, yarım yazılmış
        # bir PDF kalmaz.
        shutil.move(tmp_path, path)
    except Exception:
        logger.exception("Fatura PDF'i küçültülemedi, orijinali korunuyor: %s", path)
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)
        return {"before": before, "after": before, "compressed": False}

    after = os.path.getsize(path)
    logger.info("Fatura PDF'i küçültüldü: %s (%d -> %d bayt)", os.path.basename(path), before, after)
    return {"before": before, "after": after, "compressed": True}

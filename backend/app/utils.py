import os
import re
import time


def safe_filename(original_name: str, allowed_extensions: tuple[str, ...], default_ext: str) -> str:
    """Yüklenen dosya adını path traversal ve tehlikeli karakterlerden arındırır."""
    name = os.path.basename(original_name or f"dosya{default_ext}")
    name = re.sub(r"[^A-Za-z0-9._\-ÇĞİÖŞÜçğıöşü ]", "_", name)
    if not name.lower().endswith(allowed_extensions):
        name += default_ext
    return name


def safe_pdf_filename(original_name: str) -> str:
    return safe_filename(original_name, (".pdf",), ".pdf")


def safe_image_filename(original_name: str) -> str:
    return safe_filename(original_name, (".jpg", ".jpeg", ".png", ".heic", ".webp"), ".jpg")


def unique_destination(folder: str, filename: str) -> str:
    """Aynı isimde dosya varsa üzerine yazmak yerine zaman damgası ekler."""
    path = os.path.join(folder, filename)
    if not os.path.exists(path):
        return path
    stem, ext = os.path.splitext(filename)
    return os.path.join(folder, f"{stem}_{int(time.time())}{ext}")

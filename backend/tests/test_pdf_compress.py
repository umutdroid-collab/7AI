"""Fatura PDF'lerinin küçültülmesi.

Asıl kazanç taranmış faturalardaki gömülü görüntülerden geliyor; testler o
yolun gerçekten çalıştığını ve metin çıkarımını (fatura alanlarının okunduğu
yer) bozmadığını doğruluyor.
"""

import os

import pdfplumber
import pikepdf
import pytest
from PIL import Image, ImageDraw
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app.services import pdf_compress


def _scanned_pdf(path, tmp_path):
    """300 DPI A4 tarama taklidi: sayfanın tamamı tek bir gömülü görüntü."""
    image = Image.new("RGB", (2480, 3508), "white")
    draw = ImageDraw.Draw(image)
    for i in range(60):
        draw.text((150, 200 + i * 50), f"FATURA SATIRI {i} - 1.234,56 TL", fill=(20, 20, 20))
    png = tmp_path / "scan.png"
    image.save(png, "PNG")

    c = canvas.Canvas(str(path), pagesize=A4)
    c.drawImage(str(png), 0, 0, width=A4[0], height=A4[1])
    c.showPage()
    c.save()


def _text_pdf(path, lines=("Fatura No: MDE2026000000223", "Vade Tarihi: 22.08.2026")):
    c = canvas.Canvas(str(path), pagesize=A4)
    for i, line in enumerate(lines):
        c.drawString(40, 800 - i * 20, line)
    c.showPage()
    c.save()


def test_scanned_invoice_shrinks_a_lot(tmp_path):
    path = tmp_path / "tarama.pdf"
    _scanned_pdf(path, tmp_path)

    result = pdf_compress.compress_invoice_pdf(str(path))

    assert result["compressed"] is True
    # Ölçülen kazanç ~4 kat; yarıya inmesini şart koşmak biçim değişikliklerine
    # karşı esnek ama gerilemeyi yakalayacak kadar dar.
    assert result["after"] < result["before"] / 2


def test_embedded_image_is_downsampled_to_jpeg(tmp_path):
    path = tmp_path / "tarama.pdf"
    _scanned_pdf(path, tmp_path)
    pdf_compress.compress_invoice_pdf(str(path))

    with pikepdf.open(str(path)) as pdf:
        images = list(pdf.pages[0].get_images().values())
        assert images, "sayfada gömülü görüntü kalmadı"
        for stream in images:
            assert stream.get("/Filter") == pikepdf.Name("/DCTDecode")
            assert max(int(stream.Width), int(stream.Height)) <= pdf_compress.MAX_IMAGE_DIMENSION


def test_text_is_still_extractable_after_compression(tmp_path):
    """Fatura alanları PDF metninden okunuyor; küçültme onu bozarsa fatura
    NEEDS_REVIEW'a düşer."""
    path = tmp_path / "efatura.pdf"
    _text_pdf(path)
    pdf_compress.compress_invoice_pdf(str(path))

    with pdfplumber.open(str(path)) as pdf:
        text = pdf.pages[0].extract_text() or ""
    assert "MDE2026000000223" in text
    assert "22.08.2026" in text


def test_second_pass_leaves_the_file_alone(tmp_path):
    """`rescan` her çağrıldığında ingest_pdf tekrar çalışıyor; eşiğin altındaki
    kazanç için dosya yeniden yazılmamalı."""
    path = tmp_path / "tarama.pdf"
    _scanned_pdf(path, tmp_path)
    pdf_compress.compress_invoice_pdf(str(path))

    size_after_first = os.path.getsize(path)
    mtime = os.path.getmtime(path)
    result = pdf_compress.compress_invoice_pdf(str(path))

    assert result["compressed"] is False
    assert os.path.getsize(path) == size_after_first
    assert os.path.getmtime(path) == mtime


def test_broken_pdf_is_left_untouched(tmp_path):
    """Küçültme hatası faturayı kaybettirmemeli."""
    path = tmp_path / "bozuk.pdf"
    path.write_bytes(b"%PDF-1.4 bu bir PDF degil")

    result = pdf_compress.compress_invoice_pdf(str(path))

    assert result["compressed"] is False
    assert path.read_bytes() == b"%PDF-1.4 bu bir PDF degil"
    # Geçici dosya bırakılmamalı.
    assert list(tmp_path.iterdir()) == [path]


def test_upload_compresses_the_scan(client, admin, tmp_path):
    """Yükleme yolundan geçen taranmış fatura diske küçültülmüş inmeli."""
    path = tmp_path / "tarama.pdf"
    _scanned_pdf(path, tmp_path)
    original_size = os.path.getsize(path)

    with open(path, "rb") as f:
        r = client.post(
            "/invoices/upload",
            headers=admin,
            files={"file": ("tarama.pdf", f, "application/pdf")},
        )
    assert r.status_code == 200

    stored = r.json()
    from app.config import get_settings

    stored_path = os.path.join(get_settings().invoice_folder, stored["source_filename"])
    assert os.path.getsize(stored_path) < original_size / 2


def test_compress_existing_endpoint_reports_savings(client, admin, tmp_path):
    from app.config import get_settings

    folder = get_settings().invoice_folder
    os.makedirs(os.path.join(folder, "evobulut"), exist_ok=True)
    # Alt klasördeki EvoBulut PDF'leri de yedeğe giriyor, taranmalılar.
    _scanned_pdf(tmp_path / "kaynak.pdf", tmp_path)
    target = os.path.join(folder, "evobulut", "evobulut-1.pdf")
    with open(tmp_path / "kaynak.pdf", "rb") as src, open(target, "wb") as dst:
        dst.write(src.read())

    r = client.post("/invoices/compress-existing", headers=admin)

    assert r.status_code == 200
    body = r.json()
    assert body["taranan_pdf"] >= 1
    assert body["islenen_pdf"] >= 1
    assert body["kazanilan_mb"] >= 0


def test_compress_existing_is_admin_only(client, employee):
    assert client.post("/invoices/compress-existing", headers=employee).status_code == 403


def test_size_report_breaks_down_the_backup(client, admin):
    r = client.get("/backups/size-report", headers=admin)

    assert r.status_code == 200
    body = r.json()
    assert {f["klasor"] for f in body["klasorler"]} == {
        "invoices",
        "clinical_docs",
        "checkins",
        "vectorstore",
    }
    # En büyük klasör başta gelmeli - hangi klasöre yükleneceğini görmek için.
    sizes = [f["mb"] for f in body["klasorler"]]
    assert sizes == sorted(sizes, reverse=True)
    assert body["yerel_yedek_sayisi"] == 0


def test_size_report_is_admin_only(client, employee):
    assert client.get("/backups/size-report", headers=employee).status_code == 403


# --- Yedekleme zamanlaması -------------------------------------------------
#
# Canlıda (17.08.2026) hiç yedek alınmamış olduğu görüldü: eski
# `interval, weeks=1` işi ilk çalışmasını açılıştan bir hafta sonraya
# koyuyordu ve her deploy süreci yeniden başlatıp sayacı sıfırlıyordu.


def test_weekly_backup_is_scheduled_at_a_fixed_time(tmp_path, monkeypatch):
    """Deploy'un sayacı sıfırlayamaması için sabit saatli cron kullanılmalı."""
    from app.services import backup

    monkeypatch.setattr(backup.settings, "backup_dir", str(tmp_path), raising=False)
    scheduler = backup.start_backup_scheduler()
    try:
        job = scheduler.get_job("weekly-backup")
        assert job is not None
        assert "cron" in str(job.trigger)
    finally:
        scheduler.shutdown(wait=False)


def test_missing_backup_schedules_a_catch_up_run(tmp_path, monkeypatch):
    from app.services import backup

    monkeypatch.setattr(backup.settings, "backup_dir", str(tmp_path), raising=False)
    scheduler = backup.start_backup_scheduler()
    try:
        assert scheduler.get_job("catch-up-backup") is not None
    finally:
        scheduler.shutdown(wait=False)


def test_recent_backup_skips_the_catch_up_run(tmp_path, monkeypatch):
    """Süreç sık yeniden başlarsa telafi tekrar tekrar çalışmamalı; ölçü
    bellekteki sayaç değil diskteki en yeni yedek."""
    from app.services import backup

    monkeypatch.setattr(backup.settings, "backup_dir", str(tmp_path), raising=False)
    (tmp_path / "yedek-20260817-000000-0.zip").write_bytes(b"taze")

    scheduler = backup.start_backup_scheduler()
    try:
        assert scheduler.get_job("catch-up-backup") is None
        assert backup.newest_backup_age_days() < 1
    finally:
        scheduler.shutdown(wait=False)


def test_stale_backup_triggers_a_catch_up_run(tmp_path, monkeypatch):
    import os
    import time

    from app.services import backup

    monkeypatch.setattr(backup.settings, "backup_dir", str(tmp_path), raising=False)
    old = tmp_path / "yedek-20260101-000000-0.zip"
    old.write_bytes(b"eski")
    stale = time.time() - (backup.BACKUP_INTERVAL_DAYS + 1) * 86400
    os.utime(old, (stale, stale))

    scheduler = backup.start_backup_scheduler()
    try:
        assert scheduler.get_job("catch-up-backup") is not None
    finally:
        scheduler.shutdown(wait=False)


def test_size_report_lists_the_biggest_files(client, admin):
    """Klasör toplamı nereye bakılacağını söyler, dosya listesi neyin
    şişirdiğini."""
    import os

    from app.config import get_settings

    folder = get_settings().invoice_folder
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "buyuk.pdf"), "wb") as f:
        f.write(b"0" * 300_000)
    with open(os.path.join(folder, "kucuk.pdf"), "wb") as f:
        f.write(b"0" * 1_000)

    body = client.get("/backups/size-report", headers=admin).json()

    listed = body["en_buyuk_dosyalar"]
    names = [f["dosya"] for f in listed]
    # Vektör indeksi testler arasında diskte kalıyor ve boyutu değişken; bu
    # yüzden mutlak sıra değil, sözleşme sınanır: liste büyükten küçüğe ve
    # kayda değer dosya içinde.
    assert [f["mb"] for f in listed] == sorted((f["mb"] for f in listed), reverse=True)
    assert os.path.join("invoices", "buyuk.pdf") in names
    assert os.path.join("invoices", "kucuk.pdf") not in names[: names.index(os.path.join("invoices", "buyuk.pdf"))]

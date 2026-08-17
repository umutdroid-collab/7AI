"""Vektör indeksinin bakımı ve klinik PDF'lerin küçültülmesi.

İkisi de canlı ölçümden çıktı (17.08.2026 `size-report`): yedeğin 205 MB'ının
127'si vektör indeksi, 51'i klinik PDF'ler; faturalar yalnızca 12 MB'tı.
"""

import os

from PIL import Image, ImageDraw
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app.services import vector_store


def _image_heavy_pdf(path, tmp_path, pages=1):
    """Dergi makalesi taklidi: şekil görüntüleriyle dolu sayfalar."""
    image = Image.new("RGB", (2000, 2600), "white")
    draw = ImageDraw.Draw(image)
    for i in range(40):
        draw.text((120, 150 + i * 55), f"Figure {i}: IL-6 and TNF levels in sepsis", fill=(25, 25, 25))
    png = tmp_path / "figure.png"
    image.save(png, "PNG")

    c = canvas.Canvas(str(path), pagesize=A4)
    for _ in range(pages):
        c.drawImage(str(png), 0, 0, width=A4[0], height=A4[1])
        c.drawString(40, 30, "Efferon LPS hemoperfusion study")
        c.showPage()
    c.save()


def test_vacuum_reclaims_free_pages(client, admin, tmp_path):
    """VACUUM boşalan sayfaları geri verir. Kazanç mütevazı (yerel ölçüm ~%14);
    buradaki iddia dosyanın küçüldüğü değil, işlemin veriyi kaybetmeden
    tamamlandığı."""
    _image_heavy_pdf(tmp_path / "calisma.pdf", tmp_path)
    with open(tmp_path / "calisma.pdf", "rb") as f:
        assert client.post(
            "/assistant/documents/upload",
            headers=admin,
            files={"file": ("calisma.pdf", f, "application/pdf")},
        ).status_code == 200

    r = client.post("/assistant/vacuum-index", headers=admin)

    assert r.status_code == 200
    body = r.json()
    assert body["surekli_budama_acildi"] is True
    assert body["sonraki_mb"] <= body["onceki_mb"]


def test_vacuum_enables_continuous_pruning(client, admin):
    """Tek seferlik bir temizlik yetmez; ayar açılmazsa günlük yeniden şişer."""
    client.post("/assistant/vacuum-index", headers=admin)

    from chromadb.config import Settings as ChromaSettings, System
    from chromadb.db.impl.sqlite import SqliteDB

    from app.config import get_settings

    system = System(ChromaSettings(is_persistent=True, persist_directory=get_settings().vector_db_dir))
    system.start()
    try:
        sqlite = system.instance(SqliteDB)
        assert sqlite.config.get_parameter("automatically_purge").value is True
    finally:
        system.stop()
        vector_store.reset_client()


def test_assistant_still_answers_after_vacuum(client, admin, tmp_path):
    """VACUUM istemciyi bırakıyor; bırakılan istemci geri gelmezse asistan
    sunucu yeniden başlatılana kadar bozuk kalırdı (bkz. reset_client)."""
    _image_heavy_pdf(tmp_path / "calisma.pdf", tmp_path)
    with open(tmp_path / "calisma.pdf", "rb") as f:
        client.post(
            "/assistant/documents/upload",
            headers=admin,
            files={"file": ("calisma.pdf", f, "application/pdf")},
        )

    client.post("/assistant/vacuum-index", headers=admin)

    chunks = vector_store.query_relevant_chunks("sepsis IL-6", n_results=3)
    assert chunks, "budamadan sonra vektör araması sonuç döndürmedi"


def test_vacuum_is_admin_only(client, employee):
    assert client.post("/assistant/vacuum-index", headers=employee).status_code == 403


def test_clinical_upload_compresses_before_indexing(client, admin, tmp_path):
    """Küçültme indekslemeden SONRA yapılırsa kayıttaki boyut tutmaz ve her
    açılışta tüm külliyat yeniden gömülür."""
    from app.config import get_settings

    _image_heavy_pdf(tmp_path / "calisma.pdf", tmp_path)
    original = os.path.getsize(tmp_path / "calisma.pdf")

    with open(tmp_path / "calisma.pdf", "rb") as f:
        r = client.post(
            "/assistant/documents/upload",
            headers=admin,
            files={"file": ("calisma.pdf", f, "application/pdf")},
        )
    assert r.status_code == 200

    stored = os.path.join(get_settings().clinical_docs_folder, r.json()["filename"])
    on_disk = os.path.getsize(stored)
    assert on_disk < original
    # Kayıttaki boyut diskteki dosyayla aynı olmalı - yoksa yeniden indeksleme.
    assert r.json()["file_size"] == on_disk


def test_compress_existing_documents_updates_recorded_size(client, admin, tmp_path):
    from app.config import get_settings
    from app.models import ClinicalDocument
    from app.database import SessionLocal

    folder = get_settings().clinical_docs_folder
    os.makedirs(folder, exist_ok=True)
    _image_heavy_pdf(tmp_path / "kaynak.pdf", tmp_path)

    # Küçültme eklenmeden önce yüklenmiş bir doküman taklidi: dosya ham,
    # kayıttaki boyut da ham.
    target = os.path.join(folder, "eski-calisma.pdf")
    with open(tmp_path / "kaynak.pdf", "rb") as src, open(target, "wb") as dst:
        dst.write(src.read())
    raw_size = os.path.getsize(target)

    db = SessionLocal()
    db.add(ClinicalDocument(filename="eski-calisma.pdf", title="Eski", num_chunks=3, file_size=raw_size))
    db.commit()
    db.close()

    r = client.post("/assistant/documents/compress-existing", headers=admin)

    assert r.status_code == 200
    assert r.json()["islenen_pdf"] >= 1
    assert r.json()["kazanilan_mb"] >= 0

    db = SessionLocal()
    doc = db.query(ClinicalDocument).filter(ClinicalDocument.filename == "eski-calisma.pdf").first()
    assert doc.file_size == os.path.getsize(target)
    db.close()


def test_compressed_document_is_not_reindexed(client, admin, tmp_path):
    """Boyut kaydı güncellendiği için yeniden indeksleme dosyayı atlamalı."""
    _image_heavy_pdf(tmp_path / "calisma.pdf", tmp_path)
    with open(tmp_path / "calisma.pdf", "rb") as f:
        client.post(
            "/assistant/documents/upload",
            headers=admin,
            files={"file": ("calisma.pdf", f, "application/pdf")},
        )
    client.post("/assistant/documents/compress-existing", headers=admin)

    # reindex_all değişmemiş dokümanları atlar; 0 parça = hiçbiri yeniden
    # gömülmedi.
    assert vector_store.reindex_all() == 0


def test_document_compression_is_admin_only(client, employee):
    assert client.post("/assistant/documents/compress-existing", headers=employee).status_code == 403

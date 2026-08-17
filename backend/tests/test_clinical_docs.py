"""Klinik çalışma yükleme, listeleme, silme ve açılışta yeniden indeksleme.

Gerçek PDF üretilip gerçek embedding yapılır - indeksleme yolunun sahiden
çalıştığını (ve atlama mantığının doğru olduğunu) kanıtlamak için.
"""

import io
import os

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def make_pdf(text: str) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.drawString(72, 750, text)
    c.drawString(72, 730, "Bu bir klinik calisma ozetidir. " * 3)
    c.save()
    return buf.getvalue()


def upload(client, admin, name, text="Klinik Calisma Basligi"):
    return client.post(
        "/assistant/documents/upload",
        files={"file": (name, make_pdf(text), "application/pdf")},
        headers=admin,
    )


def test_upload_records_size_and_chunks(client, admin):
    r = upload(client, admin, "calisma1.pdf")
    assert r.status_code == 200, r.text
    doc = r.json()
    assert doc["filename"] == "calisma1.pdf"
    assert doc["num_chunks"] > 0
    assert doc["file_size"] > 0


def test_documents_list_shows_uploads(client, admin):
    upload(client, admin, "a.pdf")
    upload(client, admin, "b.pdf")
    docs = client.get("/assistant/documents", headers=admin).json()
    assert sorted(d["filename"] for d in docs) == ["a.pdf", "b.pdf"]
    assert all(d["file_size"] > 0 for d in docs)


def test_bulk_upload_reports_per_file_results(client, admin):
    r = client.post(
        "/assistant/documents/bulk-upload",
        files=[
            ("files", ("c1.pdf", make_pdf("Calisma 1"), "application/pdf")),
            ("files", ("c2.pdf", make_pdf("Calisma 2"), "application/pdf")),
            ("files", ("notpdf.txt", b"duz metin", "text/plain")),
        ],
        headers=admin,
    )
    assert r.status_code == 200
    assert r.json()["created"] == 2
    assert len(r.json()["errors"]) == 1
    assert "notpdf.txt" in r.json()["errors"][0]["file"]


def test_delete_removes_file_vectors_and_row(client, admin):
    doc = upload(client, admin, "silinecek.pdf", "Aspirin kardiyovaskulerz calisma").json()
    from app.config import get_settings
    from app.services.vector_store import get_collection

    path = os.path.join(get_settings().clinical_docs_folder, "silinecek.pdf")
    assert os.path.exists(path)
    before = get_collection().get(where={"filename": "silinecek.pdf"})
    assert len(before["ids"]) > 0

    assert client.delete(f"/assistant/documents/{doc['id']}", headers=admin).status_code == 200

    assert not os.path.exists(path)
    after = get_collection().get(where={"filename": "silinecek.pdf"})
    assert len(after["ids"]) == 0
    assert client.get("/assistant/documents", headers=admin).json() == []


def test_employee_cannot_upload_or_delete(client, admin, employee):
    doc = upload(client, admin, "korumali.pdf").json()
    r = client.post(
        "/assistant/documents/upload",
        files={"file": ("x.pdf", make_pdf("x"), "application/pdf")},
        headers=employee,
    )
    assert r.status_code == 403
    assert client.delete(f"/assistant/documents/{doc['id']}", headers=employee).status_code == 403


def test_reindex_skips_unchanged_documents(client, admin):
    """Asıl performans düzeltmesi: açılışta değişmemiş dosyalar yeniden
    gömülmemeli (yoksa her deploy doküman sayısıyla orantılı yavaşlar)."""
    from app.services.vector_store import reindex_all

    upload(client, admin, "sabit.pdf")
    assert reindex_all() == 0  # zaten indeksli -> hiçbir chunk üretilmemeli
    assert reindex_all(force=True) > 0  # zorlanınca yeniden indeksler


def test_reindex_picks_up_changed_file(client, admin):
    from app.config import get_settings
    from app.services.vector_store import reindex_all

    upload(client, admin, "degisen.pdf", "Ilk surum")
    assert reindex_all() == 0

    path = os.path.join(get_settings().clinical_docs_folder, "degisen.pdf")
    with open(path, "wb") as f:
        f.write(make_pdf("Guncellenmis surum cok daha uzun bir metin " * 20))

    assert reindex_all() > 0  # boyut değişti -> yeniden indekslenmeli


def _wait_for_rebuild(client, admin, timeout=60):
    """Yeniden üretim arka planda; teşhis ucundan bitmesini bekler."""
    import time

    deadline = time.time() + timeout
    while time.time() < deadline:
        state = client.get("/backups/restore-status", headers=admin).json()
        if not state["calisiyor"]:
            assert state["hata"] is None, state["hata"]
            return state
        time.sleep(0.2)
    raise AssertionError("vektör indeksi yeniden üretimi zaman aşımına uğradı")


def test_assistant_index_still_works_after_backup_restore(client, admin):
    """Geri yükleme vektör dizinini diskte değiştiriyor; bellekteki Chroma
    istemcisi bırakılmazsa asistan sunucu yeniden başlatılana kadar bozuk
    kalıyordu."""
    from app.services.vector_store import get_collection, query_relevant_chunks

    upload(client, admin, "once.pdf", "Aspirin kardiyovaskuler koruma calismasi")
    filename = client.post("/backups/run", headers=admin).json()["filename"]

    r = client.post(f"/backups/{filename}/restore", params={"confirm": True}, headers=admin)
    assert r.status_code == 200

    # Vektör indeksi artık yedeğe konmuyor, geri yüklemeden sonra klinik
    # PDF'lerden yeniden üretiliyor - ve bu arka planda çalışıyor.
    assert r.json()["vektor_indeksi_yeniden_uretiliyor"] is True
    _wait_for_rebuild(client, admin)

    # geri yüklemeden sonra indeks hâlâ okunabilir ve yazılabilir olmalı
    assert get_collection().count() > 0
    assert len(query_relevant_chunks("aspirin", n_results=1)) > 0

    r = upload(client, admin, "sonra.pdf", "Yeni calisma geri yuklemeden sonra")
    assert r.status_code == 200
    assert r.json()["num_chunks"] > 0

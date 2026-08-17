"""Yedeklerin dış depoya kopyalanması.

Gerçek bir S3 servisine bağlanmadan, boto3 istemcisinin yerine sahte bir
nesne konularak sınanır: önemli olan çağrının doğru yapılması ve hatanın
yerel yedeklemeyi bozmaması.
"""

import os

import pytest

from app.services import offsite_backup


class FakeS3:
    def __init__(self, fail_upload=False):
        self.uploaded: list[tuple[str, str]] = []
        self.deleted: list[str] = []
        self.objects: list[dict] = []
        self.fail_upload = fail_upload

    def upload_file(self, local_path, bucket, key):
        if self.fail_upload:
            raise RuntimeError("bağlantı koptu")
        self.uploaded.append((local_path, key))

    def list_objects_v2(self, Bucket, Prefix):
        return {"Contents": [o for o in self.objects if o["Key"].startswith(Prefix)]}

    def delete_objects(self, Bucket, Delete):
        self.deleted.extend(o["Key"] for o in Delete["Objects"])
        keys = {o["Key"] for o in Delete["Objects"]}
        self.objects = [o for o in self.objects if o["Key"] not in keys]


@pytest.fixture
def configured(monkeypatch):
    """Dış depoyu yapılandırılmış gibi gösterir ve sahte istemciyi bağlar."""
    fake = FakeS3()
    monkeypatch.setattr(offsite_backup, "is_configured", lambda: True)
    monkeypatch.setattr(offsite_backup, "_client", lambda: fake)
    return fake


def test_upload_is_skipped_when_not_configured(monkeypatch, tmp_path):
    monkeypatch.setattr(offsite_backup, "is_configured", lambda: False)
    result = offsite_backup.upload(str(tmp_path / "yok.zip"))
    assert result == {"ok": False, "reason": "yapilandirilmamis"}


def test_backup_is_uploaded_under_a_prefix(configured, tmp_path):
    path = tmp_path / "yedek-20260101-000000-0.zip"
    path.write_bytes(b"icerik")

    result = offsite_backup.upload(str(path))

    assert result["ok"] is True
    assert configured.uploaded == [(str(path), "yedekler/yedek-20260101-000000-0.zip")]
    assert result["size_bytes"] == 6


def test_upload_failure_does_not_raise(monkeypatch, tmp_path):
    """Dış kopya alınamadı diye yerel yedekleme başarısız sayılmamalı."""
    fake = FakeS3(fail_upload=True)
    monkeypatch.setattr(offsite_backup, "is_configured", lambda: True)
    monkeypatch.setattr(offsite_backup, "_client", lambda: fake)

    path = tmp_path / "yedek.zip"
    path.write_bytes(b"x")
    result = offsite_backup.upload(str(path))

    assert result["ok"] is False
    assert "bağlantı koptu" in result["reason"]


def test_old_copies_are_pruned(configured, monkeypatch):
    """Her yedek tüm yüklenen dosyaları içeriyor; budanmazsa kota dolar."""
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "backup_s3_keep_count", 3, raising=False)
    configured.objects = [
        {"Key": f"yedekler/yedek-{i}.zip", "Size": 10, "LastModified": _dt(i)} for i in range(5)
    ]

    removed = offsite_backup.prune()

    assert removed == 2
    # En eski ikisi silinmeli, en yeni üçü kalmalı.
    assert sorted(configured.deleted) == ["yedekler/yedek-0.zip", "yedekler/yedek-1.zip"]


def test_remote_list_is_newest_first(configured):
    configured.objects = [
        {"Key": "yedekler/eski.zip", "Size": 1, "LastModified": _dt(0)},
        {"Key": "yedekler/yeni.zip", "Size": 2, "LastModified": _dt(5)},
    ]
    assert [i["filename"] for i in offsite_backup.list_remote()] == ["yeni.zip", "eski.zip"]


def test_status_reports_unreachable_storage(monkeypatch):
    """Yanlış anahtar/bucket normal akışta sessizce yutuluyor; teşhis ucu
    gerçek hatayı göstermeli."""
    monkeypatch.setattr(offsite_backup, "is_configured", lambda: True)

    class Broken:
        def list_objects_v2(self, **_):
            raise RuntimeError("AccessDenied")

    monkeypatch.setattr(offsite_backup, "_client", lambda: Broken())
    status = offsite_backup.status()

    assert status["yapilandirilmis"] is True
    assert status["erisim"] is False
    assert "AccessDenied" in status["mesaj"]


def test_offsite_endpoints_are_admin_only(client, employee):
    assert client.get("/backups/offsite/status", headers=employee).status_code == 403
    assert client.get("/backups/offsite", headers=employee).status_code == 403


def test_local_backup_still_succeeds_when_offsite_is_off(client, admin):
    """Dış depo kapalıyken haftalık yedekleme aynen çalışmalı."""
    r = client.post("/backups/run", headers=admin)
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert len(client.get("/backups", headers=admin).json()) == 1


def _dt(offset: int):
    from datetime import datetime, timedelta, timezone

    return datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(days=offset)


# --- Felaket senaryosu: dış depodan geri dönüş ------------------------------
#
# Dış kopyanın var olması yetmiyor; geri yükleme yalnızca yerel klasördeki
# dosyayı okuyor. Railway diski gittiğinde içeri bir yol olmalı.


def test_offsite_copy_can_be_pulled_back_locally(client, admin, monkeypatch, tmp_path):
    from app.config import get_settings
    from app.services import offsite_backup

    class FakeDownload:
        def download_file(self, bucket, key, dest):
            assert key == "yedekler/yedek-20260101-000000-0.zip"
            with open(dest, "wb") as f:
                f.write(b"PK\x03\x04 sahte")

    monkeypatch.setattr(offsite_backup, "is_configured", lambda: True)
    monkeypatch.setattr(offsite_backup, "_client", lambda: FakeDownload())

    r = client.post("/backups/offsite/yedek-20260101-000000-0.zip/pull", headers=admin)

    assert r.status_code == 200
    dest = os.path.join(get_settings().backup_dir, "yedek-20260101-000000-0.zip")
    assert os.path.exists(dest)


def test_pull_rejects_path_traversal(monkeypatch, tmp_path):
    """Uzaktan gelen ad da güvenilmez: yalnızca dosya adı kullanılmalı."""
    from app.services import offsite_backup

    seen = {}

    class FakeDownload:
        def download_file(self, bucket, key, dest):
            seen["key"], seen["dest"] = key, dest
            open(dest, "wb").close()

    monkeypatch.setattr(offsite_backup, "is_configured", lambda: True)
    monkeypatch.setattr(offsite_backup, "_client", lambda: FakeDownload())

    offsite_backup.download("../../etc/kotu.zip", str(tmp_path))

    assert seen["key"] == "yedekler/kotu.zip"
    assert os.path.dirname(seen["dest"]) == str(tmp_path)


def test_pull_surfaces_the_real_error(client, admin, monkeypatch):
    """Yükleme sessizce yutuyor ama geri yükleme bilinçli bir işlem; hata
    kullanıcıya görünmeli."""
    from app.services import offsite_backup

    monkeypatch.setattr(offsite_backup, "is_configured", lambda: True)

    class Broken:
        def download_file(self, *_):
            raise RuntimeError("NoSuchKey")

    monkeypatch.setattr(offsite_backup, "_client", lambda: Broken())

    r = client.post("/backups/offsite/yok.zip/pull", headers=admin)
    assert r.status_code == 502
    assert "NoSuchKey" in r.json()["detail"]


def test_backup_zip_can_be_uploaded_and_restored(client, admin):
    """Dış depo da yoksa elde tutulan zip'ten dönebilmeli."""
    filename = client.post("/backups/run", headers=admin).json()["filename"]
    content = client.get(f"/backups/{filename}/download", headers=admin).content

    # Yerel kopyayı sil - disk kaybı taklidi.
    client.delete(f"/backups/{filename}", headers=admin)
    assert client.get("/backups", headers=admin).json() == []

    r = client.post(
        "/backups/upload",
        headers=admin,
        files={"file": (filename, content, "application/zip")},
    )
    assert r.status_code == 200

    restore = client.post(f"/backups/{filename}/restore", params={"confirm": True}, headers=admin)
    assert restore.status_code == 200


def test_upload_rejects_a_non_zip(client, admin):
    r = client.post(
        "/backups/upload",
        headers=admin,
        files={"file": ("yedek.zip", b"bu bir zip degil", "application/zip")},
    )
    assert r.status_code == 400


def test_recovery_endpoints_are_admin_only(client, employee):
    assert client.post("/backups/offsite/x.zip/pull", headers=employee).status_code == 403
    assert client.post(
        "/backups/upload", headers=employee, files={"file": ("a.zip", b"x", "application/zip")}
    ).status_code == 403

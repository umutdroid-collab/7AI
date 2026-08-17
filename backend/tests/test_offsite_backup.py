"""Yedeklerin dış depoya kopyalanması.

Gerçek bir S3 servisine bağlanmadan, boto3 istemcisinin yerine sahte bir
nesne konularak sınanır: önemli olan çağrının doğru yapılması ve hatanın
yerel yedeklemeyi bozmaması.
"""

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

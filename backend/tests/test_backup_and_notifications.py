"""Yedekleme/geri yükleme, kişi bazlı bildirim okundu durumu ve işlem günlüğü."""

from app.database import SessionLocal
from app.models import AuditLog, Notification


def test_backup_restores_deleted_data(client, admin):
    hospital = client.post("/hospitals", json={"name": "Yedeklenecek"}, headers=admin).json()
    filename = client.post("/backups/run", headers=admin).json()["filename"]

    client.delete(f"/hospitals/{hospital['id']}", headers=admin)
    assert client.get("/hospitals", headers=admin).json() == []

    r = client.post(f"/backups/{filename}/restore", params={"confirm": True}, headers=admin)
    assert r.status_code == 200
    assert [h["name"] for h in client.get("/hospitals", headers=admin).json()] == ["Yedeklenecek"]


def test_restore_requires_explicit_confirmation(client, admin):
    filename = client.post("/backups/run", headers=admin).json()["filename"]
    assert client.post(f"/backups/{filename}/restore", headers=admin).status_code == 400


def test_backup_filename_cannot_escape_directory(client, admin):
    assert client.get("/backups/..%2F..%2Fetc%2Fpasswd/download", headers=admin).status_code == 404


def test_notification_read_state_is_per_user(client, admin, employee):
    db = SessionLocal()
    db.add(Notification(title="Vade yaklaşıyor", message="detay"))
    db.commit()
    db.close()

    nid = client.get("/notifications", headers=admin).json()[0]["id"]
    client.post(f"/notifications/{nid}/read", headers=admin)

    assert client.get("/notifications", params={"unread_only": True}, headers=admin).json() == []
    # çalışanın kendi okunmamışı etkilenmemeli
    assert len(client.get("/notifications", params={"unread_only": True}, headers=employee).json()) == 1

    client.post("/notifications/read-all", headers=employee)
    assert client.get("/notifications", params={"unread_only": True}, headers=employee).json() == []


def test_audit_log_records_deletions_with_actor(client, admin):
    hospital = client.post("/hospitals", json={"name": "Silinecek"}, headers=admin).json()
    client.delete(f"/hospitals/{hospital['id']}", headers=admin)

    entries = client.get("/audit-logs", headers=admin).json()
    deletion = [e for e in entries if e["entity_type"] == "hospital"][0]
    assert deletion["action"] == "delete"
    assert deletion["user_name"] == "Yönetici"
    assert "Silinecek" in deletion["summary"]


def test_audit_log_rolls_back_with_failed_action(client, admin):
    """Bağlı stok yüzünden silme reddedilirse günlüğe de yazılmamalı."""
    hospital = client.post("/hospitals", json={"name": "Dolu"}, headers=admin).json()
    product = client.post("/products", json={"name": "P", "reference_no": "R"}, headers=admin).json()
    client.post(
        "/stock",
        json={"product_id": product["id"], "lot_no": "L", "skt": "2030-01-01", "hospital_id": hospital["id"]},
        headers=admin,
    )
    assert client.delete(f"/hospitals/{hospital['id']}", headers=admin).status_code == 400

    db = SessionLocal()
    assert db.query(AuditLog).filter(AuditLog.entity_type == "hospital").count() == 0
    db.close()

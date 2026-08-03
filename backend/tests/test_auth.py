"""Kimlik doğrulama, yetkilendirme ve kaba kuvvet koruması."""

from tests.conftest import auth_headers


def test_login_success_and_wrong_password(client):
    assert client.post("/auth/login", data={"username": "admin@test.com", "password": "testpass123"}).status_code == 200
    r = client.post("/auth/login", data={"username": "admin@test.com", "password": "yanlis"})
    assert r.status_code == 401


def test_login_lockout_after_five_failures(client):
    ip = {"x-forwarded-for": "5.5.5.5"}
    for _ in range(5):
        client.post("/auth/login", data={"username": "admin@test.com", "password": "yanlis"}, headers=ip)
    # kilitliyken doğru şifre bile reddedilmeli
    r = client.post("/auth/login", data={"username": "admin@test.com", "password": "testpass123"}, headers=ip)
    assert r.status_code == 429


def test_lockout_is_per_ip(client):
    for _ in range(5):
        client.post(
            "/auth/login",
            data={"username": "admin@test.com", "password": "yanlis"},
            headers={"x-forwarded-for": "6.6.6.6"},
        )
    r = client.post(
        "/auth/login",
        data={"username": "admin@test.com", "password": "testpass123"},
        headers={"x-forwarded-for": "7.7.7.7"},
    )
    assert r.status_code == 200


def test_endpoints_require_authentication(client):
    for path in ["/invoices", "/stock", "/hospitals", "/products", "/notifications"]:
        assert client.get(path).status_code == 401, path


def test_employee_cannot_use_admin_endpoints(client, admin, employee):
    hospital = client.post("/hospitals", json={"name": "H"}, headers=admin).json()
    assert client.post("/hospitals", json={"name": "X"}, headers=employee).status_code == 403
    assert client.delete(f"/hospitals/{hospital['id']}", headers=employee).status_code == 403
    assert client.get("/audit-logs", headers=employee).status_code == 403
    assert client.get("/backups", headers=employee).status_code == 403


def test_password_minimum_length_enforced(client, admin):
    r = client.post(
        "/auth/users",
        json={"full_name": "K", "email": "kisa@test.com", "password": "123", "role": "employee"},
        headers=admin,
    )
    assert r.status_code == 400


def test_deactivated_user_cannot_log_in_or_use_token(client, admin):
    client.post(
        "/auth/users",
        json={"full_name": "P", "email": "pasif@test.com", "password": "gecerlisifre1", "role": "employee"},
        headers=admin,
    )
    headers = auth_headers(client, "pasif@test.com", "gecerlisifre1", ip="8.8.8.8")
    assert client.get("/invoices", headers=headers).status_code == 200

    user_id = [u for u in client.get("/auth/users", headers=admin).json() if u["email"] == "pasif@test.com"][0]["id"]
    client.patch(f"/auth/users/{user_id}/active", json={"is_active": False}, headers=admin)

    # mevcut token da anında geçersizleşmeli
    assert client.get("/invoices", headers=headers).status_code == 401
    r = client.post(
        "/auth/login",
        data={"username": "pasif@test.com", "password": "gecerlisifre1"},
        headers={"x-forwarded-for": "8.8.8.9"},
    )
    assert r.status_code == 403


def test_timestamps_are_sent_with_utc_marker(client, admin):
    """Zaman damgaları saat dilimi işareti olmadan gönderilirse tarayıcı
    bunları yerel saat sanıyor ve İstanbul'da her şey 3 saat geride
    görünüyordu."""
    hospital = client.post("/hospitals", json={"name": "H"}, headers=admin).json()
    product = client.post("/products", json={"name": "P", "reference_no": "R"}, headers=admin).json()
    item = client.post(
        "/stock", json={"product_id": product["id"], "lot_no": "L1"}, headers=admin
    ).json()

    # Zaman damgası taşıyan başlıca uçlar
    assert item["created_at"].endswith("+00:00")
    assert client.get(f"/stock/{item['id']}/history", headers=admin).json()[0]["moved_at"].endswith("+00:00")
    assert client.post("/backups/run", headers=admin).status_code == 200
    assert client.get("/backups", headers=admin).json()[0]["created_at"].endswith("+00:00")

    # Silme işlemi bir günlük kaydı üretir; onun zaman damgası da işaretli olmalı.
    client.delete(f"/hospitals/{hospital['id']}", headers=admin)
    assert client.get("/audit-logs", headers=admin).json()[0]["created_at"].endswith("+00:00")

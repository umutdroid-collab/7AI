"""Stok akışı: hastaneye taşıma, araca alma, kullanıldı işaretleme, silme."""

from datetime import date, timedelta

import pytest


@pytest.fixture
def setup(client, admin):
    hospital = client.post("/hospitals", json={"name": "Cerrahpaşa"}, headers=admin).json()
    hospital2 = client.post("/hospitals", json={"name": "Ümraniye"}, headers=admin).json()
    product = client.post(
        "/products", json={"name": "Stent 3mm", "reference_no": "REF-1", "ubb_no": "UBB-1"}, headers=admin
    ).json()
    item = client.post(
        "/stock",
        json={
            "product_id": product["id"],
            "lot_no": "LOT1",
            "serial_no": "SER1",
            "skt": (date.today() + timedelta(days=200)).isoformat(),
        },
        headers=admin,
    ).json()
    return {"hospital": hospital, "hospital2": hospital2, "product": product, "item": item}


def test_new_stock_starts_in_warehouse(setup):
    assert setup["item"]["status"] == "in_stock"
    assert setup["item"]["hospital"] is None


def test_transfer_between_hospitals_updates_location(client, admin, setup):
    item_id = setup["item"]["id"]
    r = client.post(f"/stock/{item_id}/transfer", json={"to_hospital_id": setup["hospital"]["id"]}, headers=admin)
    assert r.json()["hospital"]["name"] == "Cerrahpaşa"
    assert r.json()["status"] == "at_hospital"

    r = client.post(f"/stock/{item_id}/transfer", json={"to_hospital_id": setup["hospital2"]["id"]}, headers=admin)
    assert r.json()["hospital"]["name"] == "Ümraniye"

    history = client.get(f"/stock/{item_id}/history", headers=admin).json()
    assert len(history) >= 3  # ilk giriş + iki taşıma


def test_transfer_to_vehicle_records_carrier(client, admin, setup):
    item_id = setup["item"]["id"]
    r = client.post(f"/stock/{item_id}/transfer", json={"to_vehicle": True}, headers=admin)
    assert r.json()["status"] == "in_vehicle"
    assert r.json()["carried_by"]["email"] == "admin@test.com"


def test_mark_used_and_filtering(client, admin, setup):
    item_id = setup["item"]["id"]
    client.post(f"/stock/{item_id}/transfer", json={"to_hospital_id": setup["hospital"]["id"]}, headers=admin)
    assert client.post(f"/stock/{item_id}/mark-used", headers=admin).json()["status"] == "used"

    # kullanılan ürün varsayılan aktif listede görünmemeli
    assert item_id not in [i["id"] for i in client.get("/stock", headers=admin).json()]
    used = client.get("/stock", params={"status": "used"}, headers=admin).json()
    assert item_id in [i["id"] for i in used]


def test_search_by_reference_and_lot(client, admin, setup):
    assert len(client.get("/stock", params={"q": "REF-1"}, headers=admin).json()) == 1
    assert len(client.get("/stock", params={"q": "LOT1"}, headers=admin).json()) == 1
    assert len(client.get("/stock", params={"q": "yokboyle"}, headers=admin).json()) == 0


def test_employee_cannot_create_or_delete_stock(client, employee, setup):
    r = client.post(
        "/stock",
        json={"product_id": setup["product"]["id"], "lot_no": "L2", "skt": date.today().isoformat()},
        headers=employee,
    )
    assert r.status_code == 403
    assert client.delete(f"/stock/{setup['item']['id']}", headers=employee).status_code == 403


def test_product_delete_blocked_while_stock_attached(client, admin, setup):
    r = client.delete(f"/products/{setup['product']['id']}", headers=admin)
    assert r.status_code == 400
    client.delete(f"/stock/{setup['item']['id']}", headers=admin)
    assert client.delete(f"/products/{setup['product']['id']}", headers=admin).status_code == 200

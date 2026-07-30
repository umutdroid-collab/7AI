"""Opsiyonel SKT, stok içe aktarımında otomatik ürün oluşturma ve
manuel hedefler + elle ilerleme düzeltmesi."""

from datetime import date, timedelta

import pytest


def upload_csv(client, admin, path, content: str):
    return client.post(
        path, files={"file": ("v.csv", content.encode("utf-8"), "text/csv")}, headers=admin
    )


# --- SKT artık zorunlu değil ---

def test_stock_can_be_created_without_skt(client, admin):
    product = client.post("/products", json={"name": "Stent", "reference_no": "R1"}, headers=admin).json()
    r = client.post("/stock", json={"product_id": product["id"], "lot_no": "LOT1"}, headers=admin)
    assert r.status_code == 200, r.text
    assert r.json()["skt"] is None
    assert r.json()["days_to_expiry"] is None


def test_stock_import_without_skt_column(client, admin):
    upload_csv(client, admin, "/products/bulk-upload", "name,reference_no\nStent,R1\n")
    body = upload_csv(client, admin, "/stock/bulk-upload", "reference_no,lot_no\nR1,LOT1\nR1,LOT2\n").json()
    assert body["created"] == 2
    assert body["errors"] == []
    assert all(i["skt"] is None for i in client.get("/stock", headers=admin).json())


def test_import_still_rejects_unreadable_skt(client, admin):
    """Boş bırakmak serbest, ama yazılıp okunamıyorsa sessizce yutulmamalı."""
    upload_csv(client, admin, "/products/bulk-upload", "name,reference_no\nStent,R1\n")
    body = upload_csv(client, admin, "/stock/bulk-upload", "reference_no,lot_no,skt\nR1,LOT1,Ocak 2027\n").json()
    assert body["created"] == 0
    assert "SKT tarihi okunamadı" in body["errors"][0]["message"]


def test_items_without_skt_sort_last_and_export_works(client, admin):
    upload_csv(client, admin, "/products/bulk-upload", "name,reference_no\nStent,R1\n")
    upload_csv(
        client, admin, "/stock/bulk-upload",
        "reference_no,lot_no,skt\nR1,YOK,\nR1,VAR,01.01.2027\n",
    )
    lots = [i["lot_no"] for i in client.get("/stock", headers=admin).json()]
    assert lots == ["VAR", "YOK"]  # SKT'si olmayan sona
    assert client.get("/stock/export", headers=admin).status_code == 200


# --- Bilinmeyen ürünler otomatik açılsın, mevcut ürün adı korunsun ---

def test_import_creates_missing_products(client, admin):
    body = upload_csv(
        client, admin, "/stock/bulk-upload",
        "reference_no,name,lot_no\nYENI-1,Yeni Stent,LOT1\nYENI-2,Baska Urun,LOT2\n",
    ).json()
    assert body["created"] == 2
    assert body["created_products"] == 2
    assert body["errors"] == []
    names = sorted(p["name"] for p in client.get("/products", headers=admin).json())
    assert names == ["Baska Urun", "Yeni Stent"]


def test_existing_product_name_wins_over_csv_name(client, admin):
    """Aynı ref no farklı ürün adıyla gelirse, ürün listesindeki ad geçerli."""
    upload_csv(client, admin, "/products/bulk-upload", "name,reference_no\nDOGRU AD,R1\n")
    body = upload_csv(
        client, admin, "/stock/bulk-upload",
        "reference_no,name,lot_no\nR1,YANLIS AD,LOT1\n",
    ).json()
    assert body["created"] == 1
    assert body["created_products"] == 0  # yeni ürün açılmamalı

    items = client.get("/stock", headers=admin).json()
    assert items[0]["product"]["name"] == "DOGRU AD"
    assert len(client.get("/products", headers=admin).json()) == 1  # kopya ürün yok


def test_same_reference_twice_in_one_file_creates_one_product(client, admin):
    body = upload_csv(
        client, admin, "/stock/bulk-upload",
        "reference_no,name,lot_no\nX-1,Urun A,L1\nX-1,Urun B,L2\n",
    ).json()
    assert body["created"] == 2
    assert body["created_products"] == 1
    products = client.get("/products", headers=admin).json()
    assert len(products) == 1
    assert products[0]["name"] == "Urun A"  # ilk görülen ad


# --- Manuel hedefler ve +/- ilerleme ---

@pytest.fixture
def period():
    today = date.today()
    return {"period_start": (today - timedelta(days=5)).isoformat(),
            "period_end": (today + timedelta(days=30)).isoformat()}


def test_manual_target_without_product(client, admin, period):
    r = client.post(
        "/targets",
        json={"title": "10 hastane ziyareti", "target_quantity": 10, **period},
        headers=admin,
    )
    assert r.status_code == 200, r.text
    target = r.json()
    assert target["product"] is None
    assert target["title"] == "10 hastane ziyareti"
    assert target["progress"] == 0


def test_target_requires_product_or_title(client, admin, period):
    r = client.post("/targets", json={"target_quantity": 5, **period}, headers=admin)
    assert r.status_code == 422


def test_admin_can_increment_and_decrement_progress(client, admin, period):
    target = client.post(
        "/targets", json={"title": "Manuel hedef", "target_quantity": 10, **period}, headers=admin
    ).json()

    for _ in range(3):
        r = client.post(f"/targets/{target['id']}/progress", json={"delta": 1}, headers=admin)
    assert r.json()["progress"] == 3

    r = client.post(f"/targets/{target['id']}/progress", json={"delta": -1}, headers=admin)
    assert r.json()["progress"] == 2


def test_progress_cannot_go_negative(client, admin, period):
    target = client.post(
        "/targets", json={"title": "H", "target_quantity": 5, **period}, headers=admin
    ).json()
    r = client.post(f"/targets/{target['id']}/progress", json={"delta": -5}, headers=admin)
    assert r.json()["progress"] == 0


def test_manual_adjustment_adds_on_top_of_recorded_usage(client, admin, period):
    """Ürüne bağlı hedefte: stok hareketlerinden gelen kullanım + elle düzeltme."""
    product = client.post("/products", json={"name": "Stent", "reference_no": "R1"}, headers=admin).json()
    item = client.post(
        "/stock", json={"product_id": product["id"], "lot_no": "L1", "quantity": 2}, headers=admin
    ).json()
    client.post(f"/stock/{item['id']}/mark-used", headers=admin)

    target = client.post(
        "/targets", json={"product_id": product["id"], "target_quantity": 10, **period}, headers=admin
    ).json()
    assert target["progress"] == 2  # kullanımdan otomatik

    r = client.post(f"/targets/{target['id']}/progress", json={"delta": 1}, headers=admin)
    assert r.json()["progress"] == 3  # 2 otomatik + 1 elle
    assert r.json()["manual_progress"] == 1


def test_admin_can_edit_target(client, admin, period):
    target = client.post(
        "/targets", json={"title": "Eski", "target_quantity": 5, **period}, headers=admin
    ).json()
    r = client.patch(
        f"/targets/{target['id']}",
        json={"title": "Yeni baslik", "target_quantity": 20, "note": "guncellendi"},
        headers=admin,
    )
    assert r.status_code == 200
    assert r.json()["title"] == "Yeni baslik"
    assert r.json()["target_quantity"] == 20


def test_employee_cannot_edit_or_adjust(client, admin, employee, period):
    target = client.post(
        "/targets", json={"title": "H", "target_quantity": 5, **period}, headers=admin
    ).json()
    assert client.patch(f"/targets/{target['id']}", json={"target_quantity": 1}, headers=employee).status_code == 403
    assert client.post(f"/targets/{target['id']}/progress", json={"delta": 1}, headers=employee).status_code == 403

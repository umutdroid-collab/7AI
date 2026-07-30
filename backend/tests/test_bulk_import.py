"""Toplu CSV içe aktarma: hata mesajlarının gerçekten yol gösterici olması."""

import pytest


def upload_csv(client, admin, path, content: str, filename="veri.csv"):
    return client.post(
        path,
        files={"file": (filename, content.encode("utf-8"), "text/csv")},
        headers=admin,
    )


def test_stock_import_without_products_creates_them(client, admin):
    """Ürünler önceden yüklenmemişse stok içe aktarımı artık durmuyor;
    eksik ürünler ref no'dan otomatik açılıyor."""
    csv = "reference_no,lot_no,skt\nREF-1,LOT1,01.01.2027\nREF-2,LOT2,02.02.2027\n"
    r = upload_csv(client, admin, "/stock/bulk-upload", csv)
    assert r.status_code == 200
    body = r.json()
    assert body["created"] == 2
    assert body["created_products"] == 2
    assert body["errors"] == []
    # Ad sütunu yoksa ref no ürün adı olarak kullanılır - kullanıcı sonradan düzeltebilir.
    assert sorted(p["reference_no"] for p in client.get("/products", headers=admin).json()) == ["REF-1", "REF-2"]


def test_stock_import_reports_unknown_hospital(client, admin):
    upload_csv(client, admin, "/products/bulk-upload", "name,reference_no\nStent,REF-1\n")
    csv = "reference_no,lot_no,skt,hospital_name\nREF-1,LOT1,01.01.2027,Olmayan Hastane\n"
    body = upload_csv(client, admin, "/stock/bulk-upload", csv).json()
    assert body["created"] == 0
    assert "Hastane" in body["errors"][0]["message"]


def test_stock_import_reports_bad_date(client, admin):
    upload_csv(client, admin, "/products/bulk-upload", "name,reference_no\nStent,REF-1\n")
    csv = "reference_no,lot_no,skt\nREF-1,LOT1,Ocak 2027\n"
    body = upload_csv(client, admin, "/stock/bulk-upload", csv).json()
    assert "SKT tarihi okunamadı" in body["errors"][0]["message"]


def test_unrecognized_headers_give_one_clear_error_not_per_row(client, admin):
    """Yanlış başlıklı bir dosyada yüzlerce özdeş satır hatası yerine tek
    ve ne yapılacağını söyleyen bir mesaj dönmeli."""
    csv = "urun_kodu;parti;son_kullanma\nABC;L1;01.01.2027\nDEF;L2;01.01.2027\n"
    r = upload_csv(client, admin, "/stock/bulk-upload", csv)
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert "sütun başlıkları tanınmadı" in detail
    assert "reference_no" in detail  # ne beklendiğini söylemeli
    assert "urun_kodu" in detail  # dosyada ne bulunduğunu da söylemeli


@pytest.mark.parametrize("delimiter", [",", ";"])
def test_both_comma_and_semicolon_files_work(client, admin, delimiter):
    """Türkçe Excel CSV'yi noktalı virgülle kaydeder."""
    header = delimiter.join(["name", "reference_no"])
    row = delimiter.join(["Stent 3mm", "REF-X"])
    r = upload_csv(client, admin, "/products/bulk-upload", f"{header}\n{row}\n")
    assert r.json()["created"] == 1


def test_successful_stock_import_end_to_end(client, admin):
    upload_csv(client, admin, "/hospitals/bulk-upload", "name\nCerrahpaşa\n")
    upload_csv(client, admin, "/products/bulk-upload", "name,reference_no\nStent,REF-1\n")
    csv = (
        "reference_no,lot_no,skt,serial_no,quantity,hospital_name\n"
        "REF-1,LOT1,01.01.2027,SER1,2,Cerrahpaşa\n"
        "REF-1,LOT2,2027-06-15,,1,\n"
    )
    body = upload_csv(client, admin, "/stock/bulk-upload", csv).json()
    assert body["created"] == 2
    assert body["errors"] == []

    items = client.get("/stock", headers=admin).json()
    at_hospital = [i for i in items if i["hospital"]]
    in_stock = [i for i in items if not i["hospital"]]
    assert at_hospital[0]["hospital"]["name"] == "Cerrahpaşa"
    assert at_hospital[0]["quantity"] == 2
    assert in_stock[0]["skt"] == "2027-06-15"

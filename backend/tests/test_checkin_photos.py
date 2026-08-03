"""Check-in fotoğraflarının sunucuda küçültülmesi.

Railway diski küçük ve yedeklenmiyor; telefondan gelen ham fotoğraf birkaç MB
tutuyor. Testler gerçek JPEG üretip gerçekten küçüldüğünü doğrular.
"""

import io
import os

from PIL import Image

from app.services import images


def make_photo(width=3000, height=2000) -> bytes:
    """Sıkışmayı zorlaştırmak için düz renk yerine gradyan üretir; düz renkli
    bir görüntü zaten çok küçük çıkar ve test hiçbir şey kanıtlamaz."""
    image = Image.new("RGB", (width, height))
    pixels = image.load()
    for y in range(0, height, 4):
        for x in range(0, width, 4):
            color = ((x * 7) % 256, (y * 13) % 256, ((x + y) * 3) % 256)
            for dy in range(4):
                for dx in range(4):
                    if x + dx < width and y + dy < height:
                        pixels[x + dx, y + dy] = color
    buf = io.BytesIO()
    image.save(buf, "JPEG", quality=95)
    return buf.getvalue()


def create_checkin(client, headers, photo: bytes | None = None):
    hospital = client.post("/hospitals", json={"name": "H"}, headers=headers).json()
    return client.post(
        "/checkins",
        data={"hospital_id": hospital["id"]},
        files={"photo": ("checkin.jpg", photo if photo is not None else make_photo(), "image/jpeg")},
        headers=headers,
    )


def test_uploaded_photo_is_shrunk_on_the_server(client, admin):
    original = make_photo()
    r = create_checkin(client, admin, original)
    assert r.status_code == 200, r.text

    from app.database import SessionLocal
    from app.models import CheckIn

    db = SessionLocal()
    try:
        stored_path = db.query(CheckIn).one().photo_path
    finally:
        db.close()

    stored_size = os.path.getsize(stored_path)
    assert stored_size < len(original) / 4, (stored_size, len(original))

    with Image.open(stored_path) as saved:
        assert max(saved.size) <= images.MAX_DIMENSION


def test_preview_is_smaller_than_full_size(client, admin):
    checkin = create_checkin(client, admin).json()

    full = client.get(f"/checkins/{checkin['id']}/photo", headers=admin)
    preview = client.get(f"/checkins/{checkin['id']}/photo", params={"boyut": "onizleme"}, headers=admin)

    assert full.status_code == 200 and preview.status_code == 200
    assert len(preview.content) < len(full.content)
    with Image.open(io.BytesIO(preview.content)) as img:
        assert max(img.size) <= images.THUMB_DIMENSION


def test_preview_is_generated_for_photos_uploaded_before_this_feature(client, admin):
    """Eski kayıtların önizlemesi yok; toplu dönüşüm beklemeden ilk
    görüntülemede üretilmeli."""
    checkin = create_checkin(client, admin).json()

    from app.database import SessionLocal
    from app.models import CheckIn

    db = SessionLocal()
    try:
        photo_path = db.query(CheckIn).one().photo_path
    finally:
        db.close()

    os.remove(images.thumbnail_path(photo_path))
    r = client.get(f"/checkins/{checkin['id']}/photo", params={"boyut": "onizleme"}, headers=admin)
    assert r.status_code == 200
    assert os.path.exists(images.thumbnail_path(photo_path))


def test_corrupt_image_does_not_lose_the_checkin(client, admin):
    """Fotoğraf küçültülemedi diye check-in kaydı kaybedilmemeli."""
    r = create_checkin(client, admin, b"bu bir JPEG degil")
    assert r.status_code == 200
    assert len(client.get("/checkins", headers=admin).json()) == 1


def test_deleting_a_checkin_removes_preview_too(client, admin):
    checkin = create_checkin(client, admin).json()

    from app.database import SessionLocal
    from app.models import CheckIn

    db = SessionLocal()
    try:
        photo_path = db.query(CheckIn).one().photo_path
    finally:
        db.close()

    assert os.path.exists(images.thumbnail_path(photo_path))
    assert client.delete(f"/checkins/{checkin['id']}", headers=admin).status_code == 200
    assert not os.path.exists(photo_path)
    assert not os.path.exists(images.thumbnail_path(photo_path))


def test_employee_cannot_view_another_employees_photo(client, admin, employee):
    checkin = create_checkin(client, admin).json()
    assert client.get(f"/checkins/{checkin['id']}/photo", headers=employee).status_code == 403
    r = client.get(f"/checkins/{checkin['id']}/photo", params={"boyut": "onizleme"}, headers=employee)
    assert r.status_code == 403


def test_bulk_compression_reports_reclaimed_space(client, admin):
    create_checkin(client, admin)
    r = client.post("/checkins/compress-existing", headers=admin)
    assert r.status_code == 200
    assert r.json()["islenen_fotograf"] == 1
    assert r.json()["kazanilan_mb"] >= 0


def test_bulk_compression_is_admin_only(client, admin, employee):
    assert client.post("/checkins/compress-existing", headers=employee).status_code == 403

"""Excel'den kaydedilen CSV dosyalarıyla toplu hastane/stok girişi.

Admin, bilgisayarında bir Excel/Google Sheets tablosu hazırlayıp CSV olarak
kaydeder ve /docs üzerinden (veya mobil uygulamadan) yükler. Tek tek elle
girmek yerine yüzlerce satırı tek seferde işler.
"""

import csv
import io
from dataclasses import dataclass, field
from datetime import date, datetime

from sqlalchemy.orm import Session

from app.models import Hospital, MovementType, Product, StockItem, StockItemStatus, StockMovement, User


@dataclass
class ImportResult:
    created: int = 0
    skipped: int = 0
    errors: list[dict] = field(default_factory=list)


class CsvFormatError(Exception):
    """Dosyanın tamamı okunamıyor (yanlış sütun başlıkları vb.) - satır satır
    hata üretmek yerine tek ve anlaşılır bir mesaj vermek için."""


def _read_rows(csv_bytes: bytes, required_columns: set[str]) -> list[dict]:
    try:
        text = csv_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        # Türkçe Excel bazen Windows-1254 ile kaydeder.
        text = csv_bytes.decode("windows-1254", errors="replace")

    sample = text[:2048]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel

    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    headers = {(h or "").strip().lower() for h in (reader.fieldnames or [])}

    # Zorunlu sütunların hiçbiri yoksa dosya baştan yanlış: her satır için
    # aynı hatayı üretmek yerine ne beklendiğini tek seferde söyle.
    missing = required_columns - headers
    if missing == required_columns:
        found = ", ".join(sorted(h for h in headers if h)) or "(başlık okunamadı)"
        raise CsvFormatError(
            f"CSV sütun başlıkları tanınmadı. Beklenen sütunlar: "
            f"{', '.join(sorted(required_columns))}. Dosyada bulunanlar: {found}. "
            f"İlk satırın sütun başlıkları olduğundan emin olun."
        )

    normalized_rows = []
    for row in reader:
        normalized_rows.append({(k or "").strip().lower(): (v or "").strip() for k, v in row.items()})
    return normalized_rows


def _parse_flexible_date(raw: str) -> date | None:
    raw = raw.strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def import_hospitals_csv(csv_bytes: bytes, db: Session) -> ImportResult:
    result = ImportResult()
    rows = _read_rows(csv_bytes, {"name"})
    existing_names = {h.name.strip().lower() for h in db.query(Hospital).all()}

    for idx, row in enumerate(rows, start=2):
        name = row.get("name", "")
        if not name:
            result.errors.append({"row": idx, "message": "Hastane adı boş olamaz"})
            continue
        if name.strip().lower() in existing_names:
            result.skipped += 1
            continue
        hospital = Hospital(
            name=name,
            city=row.get("city") or None,
            address=row.get("address") or None,
            contact_person=row.get("contact_person") or None,
            contact_phone=row.get("contact_phone") or None,
        )
        db.add(hospital)
        existing_names.add(name.strip().lower())
        result.created += 1

    db.commit()
    return result


def import_products_csv(csv_bytes: bytes, db: Session) -> ImportResult:
    result = ImportResult()
    rows = _read_rows(csv_bytes, {"name", "reference_no"})
    existing_refs = {p.reference_no.strip().lower() for p in db.query(Product).all()}

    for idx, row in enumerate(rows, start=2):
        name = row.get("name", "")
        reference_no = row.get("reference_no", "")
        if not name or not reference_no:
            result.errors.append({"row": idx, "message": "name ve reference_no zorunludur"})
            continue
        if reference_no.strip().lower() in existing_refs:
            result.skipped += 1
            continue
        product = Product(
            name=name,
            reference_no=reference_no,
            ubb_no=row.get("ubb_no") or None,
            sut_kodu=row.get("sut_kodu") or None,
            manufacturer=row.get("manufacturer") or None,
            unit=row.get("unit") or None,
            notes=row.get("notes") or None,
        )
        db.add(product)
        existing_refs.add(reference_no.strip().lower())
        result.created += 1

    db.commit()
    return result


def import_stock_csv(csv_bytes: bytes, db: Session, user: User) -> ImportResult:
    result = ImportResult()
    rows = _read_rows(csv_bytes, {"reference_no", "lot_no", "skt"})

    products_by_ref = {p.reference_no.strip().lower(): p for p in db.query(Product).all()}
    hospitals_by_name = {h.name.strip().lower(): h for h in db.query(Hospital).all()}

    for idx, row in enumerate(rows, start=2):
        reference_no = row.get("reference_no", "")
        lot_no = row.get("lot_no", "")
        skt_raw = row.get("skt", "")

        if not reference_no or not lot_no or not skt_raw:
            result.errors.append({"row": idx, "message": "reference_no, lot_no ve skt zorunludur"})
            continue

        product = products_by_ref.get(reference_no.strip().lower())
        if not product:
            result.errors.append({"row": idx, "message": f"Ref no '{reference_no}' ile eşleşen ürün bulunamadı"})
            continue

        skt = _parse_flexible_date(skt_raw)
        if not skt:
            result.errors.append({"row": idx, "message": f"SKT tarihi okunamadı: '{skt_raw}'"})
            continue

        hospital_name = row.get("hospital_name", "")
        hospital = None
        if hospital_name:
            hospital = hospitals_by_name.get(hospital_name.strip().lower())
            if not hospital:
                result.errors.append({"row": idx, "message": f"Hastane '{hospital_name}' bulunamadı"})
                continue

        quantity_raw = row.get("quantity", "")
        try:
            quantity = int(quantity_raw) if quantity_raw else 1
        except ValueError:
            quantity = 1

        item = StockItem(
            product_id=product.id,
            lot_no=lot_no,
            serial_no=row.get("serial_no") or None,
            skt=skt,
            quantity=quantity,
            hospital_id=hospital.id if hospital else None,
            status=StockItemStatus.AT_HOSPITAL if hospital else StockItemStatus.IN_STOCK,
        )
        db.add(item)
        db.flush()
        db.add(StockMovement(
            stock_item_id=item.id,
            movement_type=MovementType.DISPATCH if hospital else MovementType.ADJUSTMENT,
            from_hospital_id=None,
            to_hospital_id=hospital.id if hospital else None,
            moved_by_user_id=user.id,
            note="Toplu içe aktarma",
        ))
        result.created += 1

    db.commit()
    return result

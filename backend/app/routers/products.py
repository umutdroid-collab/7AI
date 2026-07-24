from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, require_admin
from app.models import Product, User
from app.schemas import ProductBulkDelete, ProductCreate, ProductOut
from app.services.bulk_import import import_products_csv

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=list[ProductOut])
def list_products(q: str | None = None, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    query = db.query(Product)
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                Product.name.ilike(like),
                Product.reference_no.ilike(like),
                Product.ubb_no.ilike(like),
                Product.sut_kodu.ilike(like),
            )
        )
    return query.order_by(Product.name).all()


@router.post("", response_model=ProductOut)
def create_product(payload: ProductCreate, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    product = Product(**payload.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.post("/bulk-upload")
async def bulk_upload_products(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """CSV sütunları: name, reference_no (zorunlu), ubb_no, sut_kodu, manufacturer, unit, notes.
    Aynı ref no'ya sahip ürün zaten varsa o satır atlanır."""
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Sadece CSV dosyası yükleyebilirsiniz")
    content = await file.read()
    result = import_products_csv(content, db)
    return {"created": result.created, "skipped": result.skipped, "errors": result.errors}


@router.post("/bulk-delete")
def bulk_delete_products(
    payload: ProductBulkDelete, db: Session = Depends(get_db), _: User = Depends(require_admin)
):
    """Birden fazla ürünü tek seferde siler (örn. yanlışlıkla yapılan bir toplu
    yüklemeyi geri almak için). Bağlı stok kaydı olan ürünler atlanır, hata sayılmaz."""
    deleted = 0
    errors: list[dict] = []
    for product_id in payload.ids:
        product = db.get(Product, product_id)
        if not product:
            errors.append({"id": product_id, "message": "Ürün bulunamadı"})
            continue
        if product.stock_items:
            errors.append({"id": product_id, "message": f"'{product.name}': bağlı stok kayıtları var"})
            continue
        db.delete(product)
        deleted += 1
    db.commit()
    return {"deleted": deleted, "errors": errors}


@router.put("/{product_id}", response_model=ProductOut)
def update_product(product_id: int, payload: ProductCreate, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Ürün bulunamadı")
    for key, value in payload.model_dump().items():
        setattr(product, key, value)
    db.commit()
    db.refresh(product)
    return product


@router.delete("/{product_id}")
def delete_product(product_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Ürün bulunamadı")
    if product.stock_items:
        raise HTTPException(
            status_code=400,
            detail="Bu ürüne bağlı stok kayıtları var, önce onları silin",
        )
    db.delete(product)
    db.commit()
    return {"ok": True}

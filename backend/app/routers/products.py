from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, require_admin
from app.models import Product, User
from app.schemas import ProductCreate, ProductOut

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=list[ProductOut])
def list_products(q: str | None = None, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    query = db.query(Product)
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(Product.name.ilike(like), Product.reference_no.ilike(like), Product.ubb_no.ilike(like))
        )
    return query.order_by(Product.name).all()


@router.post("", response_model=ProductOut)
def create_product(payload: ProductCreate, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    product = Product(**payload.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


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

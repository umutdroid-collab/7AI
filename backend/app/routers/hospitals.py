from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, require_admin
from app.models import Hospital, User
from app.schemas import HospitalCreate, HospitalOut

router = APIRouter(prefix="/hospitals", tags=["hospitals"])


@router.get("", response_model=list[HospitalOut])
def list_hospitals(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(Hospital).order_by(Hospital.name).all()


@router.post("", response_model=HospitalOut)
def create_hospital(payload: HospitalCreate, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    hospital = Hospital(**payload.model_dump())
    db.add(hospital)
    db.commit()
    db.refresh(hospital)
    return hospital


@router.put("/{hospital_id}", response_model=HospitalOut)
def update_hospital(hospital_id: int, payload: HospitalCreate, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    hospital = db.get(Hospital, hospital_id)
    if not hospital:
        raise HTTPException(status_code=404, detail="Hastane bulunamadı")
    for key, value in payload.model_dump().items():
        setattr(hospital, key, value)
    db.commit()
    db.refresh(hospital)
    return hospital


@router.delete("/{hospital_id}")
def delete_hospital(hospital_id: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    hospital = db.get(Hospital, hospital_id)
    if not hospital:
        raise HTTPException(status_code=404, detail="Hastane bulunamadı")
    if hospital.stock_items:
        raise HTTPException(
            status_code=400,
            detail="Bu hastanede kayıtlı stok ürünleri var, önce onları taşıyın veya iade edin",
        )
    db.delete(hospital)
    db.commit()
    return {"ok": True}

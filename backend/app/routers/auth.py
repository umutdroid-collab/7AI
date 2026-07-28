import threading
import time

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.auth import create_access_token, hash_password, verify_password
from app.database import get_db
from app.deps import get_current_user, require_admin
from app.models import User
from app.schemas import PasswordChange, Token, UserActiveUpdate, UserCreate, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])

# Kaba kuvvet (brute-force) koruması: aynı e-posta+IP için kısa sürede çok
# fazla hatalı deneme yapılırsa girişi geçici olarak kilitler. Tek sunuculu
# kurulum için bellek-içi tutmak yeterli; sunucu yeniden başlarsa sayaç
# sıfırlanır, bu kabul edilebilir bir ödünleşim.
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_WINDOW_SECONDS = 15 * 60

_failed_logins: dict[str, list[float]] = {}
_failed_logins_lock = threading.Lock()


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _attempt_key(email: str, request: Request) -> str:
    return f"{email.lower()}|{_client_ip(request)}"


def _is_locked_out(key: str) -> bool:
    now = time.monotonic()
    with _failed_logins_lock:
        attempts = [t for t in _failed_logins.get(key, []) if now - t < LOCKOUT_WINDOW_SECONDS]
        _failed_logins[key] = attempts
        return len(attempts) >= MAX_FAILED_ATTEMPTS


def _record_failed_login(key: str) -> None:
    with _failed_logins_lock:
        _failed_logins.setdefault(key, []).append(time.monotonic())


def _clear_failed_logins(key: str) -> None:
    with _failed_logins_lock:
        _failed_logins.pop(key, None)


@router.post("/login", response_model=Token)
def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    key = _attempt_key(form_data.username, request)
    if _is_locked_out(key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Çok fazla hatalı giriş denemesi yapıldı. Lütfen 15 dakika sonra tekrar deneyin.",
        )

    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        _record_failed_login(key)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="E-posta veya şifre hatalı")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Kullanıcı pasif")
    _clear_failed_logins(key)
    token = create_access_token(subject=user.email)
    return Token(access_token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.post("/users", response_model=UserOut)
def create_user(payload: UserCreate, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    if len(payload.password) < 8:
        raise HTTPException(status_code=400, detail="Şifre en az 8 karakter olmalı")
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Bu e-posta zaten kayıtlı")
    user = User(
        full_name=payload.full_name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    return db.query(User).order_by(User.full_name).all()


@router.post("/change-password", response_model=UserOut)
def change_password(
    payload: PasswordChange,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Mevcut şifre hatalı")
    if len(payload.new_password) < 8:
        raise HTTPException(status_code=400, detail="Yeni şifre en az 8 karakter olmalı")
    user.hashed_password = hash_password(payload.new_password)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/users/{user_id}/active", response_model=UserOut)
def set_user_active(
    user_id: int,
    payload: UserActiveUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if user_id == admin.id and not payload.is_active:
        raise HTTPException(status_code=400, detail="Kendi hesabınızı pasifleştiremezsiniz")
    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")
    target.is_active = payload.is_active
    db.commit()
    db.refresh(target)
    return target

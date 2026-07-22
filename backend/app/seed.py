import logging
import os

from app.auth import hash_password
from app.database import SessionLocal
from app.models import User, UserRole

logger = logging.getLogger("seed")


def seed_default_admin() -> None:
    email = os.environ.get("SEED_ADMIN_EMAIL", "admin@sirket.com")
    password = os.environ.get("SEED_ADMIN_PASSWORD", "DegistirilecekSifre123!")

    db = SessionLocal()
    try:
        if db.query(User).count() > 0:
            return
        admin = User(
            full_name="Yönetici",
            email=email,
            hashed_password=hash_password(password),
            role=UserRole.ADMIN,
        )
        db.add(admin)
        db.commit()
        logger.warning(
            "Varsayılan yönetici oluşturuldu: %s / %s -- İLK GİRİŞTEN SONRA ŞİFREYİ DEĞİŞTİRİN",
            email,
            password,
        )
    finally:
        db.close()

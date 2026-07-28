"""İşlem günlüğü yardımcısı.

Günlük kaydı hiçbir zaman asıl işlemi bozmamalı: kayıt tutulamazsa hata
yükseltmek yerine loglanır - kullanıcının silme/güncelleme işlemi başarılı
olmuşken "günlüğe yazılamadı" diye 500 dönmek daha kötü olurdu.
"""

import logging

from sqlalchemy.orm import Session

from app.models import AuditLog, User

logger = logging.getLogger("audit")


def record(
    db: Session,
    user: User | None,
    action: str,
    entity_type: str,
    entity_id: str | int | None,
    summary: str,
) -> None:
    """Günlük kaydını oturuma ekler. commit çağırmaz - çağıran taraf zaten
    kendi işlemini commit ederken bu da aynı işlemle yazılır, böylece asıl
    işlem geri alınırsa günlük kaydı da geri alınır."""
    try:
        db.add(
            AuditLog(
                user_id=user.id if user else None,
                user_name=user.full_name if user else "sistem",
                action=action,
                entity_type=entity_type,
                entity_id=str(entity_id) if entity_id is not None else None,
                summary=summary,
            )
        )
    except Exception:
        logger.exception("İşlem günlüğü kaydı oluşturulamadı: %s %s", action, entity_type)

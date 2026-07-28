from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_admin
from app.models import AuditLog, User
from app.schemas import AuditLogOut

router = APIRouter(prefix="/audit-logs", tags=["audit"])


@router.get("", response_model=list[AuditLogOut])
def list_audit_logs(
    entity_type: str | None = None,
    limit: int = 200,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    query = db.query(AuditLog)
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)
    return query.order_by(AuditLog.created_at.desc()).limit(min(limit, 500)).all()

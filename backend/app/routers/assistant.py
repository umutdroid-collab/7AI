from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, require_admin
from app.models import ClinicalDocument, User
from app.schemas import ChatRequest, ChatResponse, ClinicalDocumentOut
from app.services.rag import answer_question
from app.services.vector_store import reindex_all

router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    answer, sources, was_answered = answer_question(db, payload.question, user.id)
    return ChatResponse(answer=answer, sources=sources, was_answered=was_answered)


@router.get("/documents", response_model=list[ClinicalDocumentOut])
def list_documents(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return db.query(ClinicalDocument).order_by(ClinicalDocument.filename).all()


@router.post("/reindex")
def reindex(_: User = Depends(require_admin)):
    total_chunks = reindex_all()
    return {"ok": True, "total_chunks": total_chunks}

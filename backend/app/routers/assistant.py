import os
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.deps import get_current_user, require_admin
from app.models import ClinicalDocument, User
from app.schemas import ChatRequest, ChatResponse, ClinicalDocumentOut
from app.services.rag import answer_question
from app.services.vector_store import index_pdf, reindex_all
from app.utils import safe_pdf_filename, unique_destination

router = APIRouter(prefix="/assistant", tags=["assistant"])
settings = get_settings()


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


MAX_UPLOAD_BYTES = 30 * 1024 * 1024


@router.post("/documents/upload", response_model=ClinicalDocumentOut)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Klinik çalışma klasörüne fiziksel erişimi olmayan (örn. bulutta
    barındırılan) kurulumlarda, PDF'i doğrudan uygulamadan yükleyip
    indekslemeyi tetiklemek için kullanılır."""
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Sadece PDF dosyası yükleyebilirsiniz")

    folder = settings.clinical_docs_folder
    os.makedirs(folder, exist_ok=True)
    dest_path = unique_destination(folder, safe_pdf_filename(file.filename))

    size = 0
    with open(dest_path, "wb") as out:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                out.close()
                os.remove(dest_path)
                raise HTTPException(status_code=400, detail="Dosya çok büyük (maksimum 30 MB)")
            out.write(chunk)

    index_pdf(Path(dest_path))

    doc = db.query(ClinicalDocument).filter(ClinicalDocument.filename == os.path.basename(dest_path)).first()
    if not doc:
        raise HTTPException(status_code=500, detail="Doküman indekslenemedi")
    return doc

import os
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.deps import get_current_user, require_admin
from app.models import ClinicalDocument, User
from app.schemas import ChatRequest, ChatResponse, ClinicalDocumentOut
import logging

from app.services import audit
from app.services.pubmed import _raw_search as pubmed_raw_search
from app.services.rag import answer_question
from app.services.vector_store import index_pdf, reindex_all, remove_document
from app.utils import safe_pdf_filename, unique_destination

logger = logging.getLogger("assistant")

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


@router.get("/pubmed-diagnostics")
def pubmed_diagnostics(_: User = Depends(require_admin)):
    """PubMed (NCBI) bağlantısını test eder ve gerçek hatayı (varsa) döner -
    normal sohbet akışında bu hata sessizce yutulup kaynaksız cevap verilir,
    burada asıl nedeni (bağlantı, zaman aşımı, yetkilendirme vb.) görmek için."""
    try:
        results = pubmed_raw_search("aspirin", 1)
        return {
            "ok": True,
            "message": f"NCBI PubMed'e başarıyla bağlanıldı ({len(results)} sonuç).",
            "sample": results[0] if results else None,
            "pubmed_email_set": bool(settings.pubmed_email),
            "pubmed_api_key_set": bool(settings.pubmed_api_key),
        }
    except Exception as e:
        return {
            "ok": False,
            "message": f"{type(e).__name__}: {e}",
            "pubmed_email_set": bool(settings.pubmed_email),
            "pubmed_api_key_set": bool(settings.pubmed_api_key),
        }


MAX_UPLOAD_BYTES = 30 * 1024 * 1024


async def _save_and_index(file: UploadFile, db: Session) -> ClinicalDocument:
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail=f"'{file.filename}': sadece PDF dosyası yükleyebilirsiniz")

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
                raise HTTPException(status_code=400, detail=f"'{file.filename}': dosya çok büyük (maksimum 30 MB)")
            out.write(chunk)

    index_pdf(Path(dest_path))

    doc = db.query(ClinicalDocument).filter(ClinicalDocument.filename == os.path.basename(dest_path)).first()
    if not doc:
        raise HTTPException(status_code=500, detail=f"'{file.filename}': doküman indekslenemedi")
    return doc


@router.post("/documents/upload", response_model=ClinicalDocumentOut)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Klinik çalışma klasörüne fiziksel erişimi olmayan (örn. bulutta
    barındırılan) kurulumlarda, PDF'i doğrudan uygulamadan yükleyip
    indekslemeyi tetiklemek için kullanılır."""
    return await _save_and_index(file, db)


@router.post("/documents/bulk-upload")
async def bulk_upload_documents(
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Birden fazla klinik çalışmayı tek seferde yükler. Her dosya ayrı ayrı
    işlenir; biri başarısız olursa diğerleri etkilenmez."""
    created = 0
    errors = []
    for file in files:
        try:
            await _save_and_index(file, db)
            created += 1
        except HTTPException as e:
            errors.append({"file": file.filename, "message": e.detail})
        except Exception:
            logger.exception("Klinik çalışma yüklenemedi: %s", file.filename)
            errors.append({"file": file.filename, "message": "Dosya işlenemedi"})
    return {"created": created, "errors": errors}


@router.delete("/documents/{document_id}")
def delete_document(document_id: int, db: Session = Depends(get_db), user: User = Depends(require_admin)):
    """Klinik çalışmayı hem diskten, hem vektör indeksinden, hem de kayıttan
    siler - aksi halde asistan silinmiş bir çalışmadan alıntı yapmaya devam
    ederdi."""
    doc = db.get(ClinicalDocument, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Klinik çalışma bulunamadı")

    remove_document(doc.filename)

    file_path = os.path.join(settings.clinical_docs_folder, doc.filename)
    if os.path.exists(file_path):
        os.remove(file_path)

    audit.record(db, user, "delete", "clinical_document", document_id, f"Klinik çalışma silindi: {doc.filename}")
    db.delete(doc)
    db.commit()
    return {"ok": True}

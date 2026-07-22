"""Klinik çalışma PDF'lerini parçalayıp yerel bir Chroma vektör veritabanında
indeksler. Embedding için chromadb'nin varsayılan (onnxruntime tabanlı,
tamamen yerel/ücretsiz) MiniLM modelini kullanır; harici bir API anahtarı
gerekmez."""

import logging
from pathlib import Path

import chromadb
import pdfplumber
from chromadb.utils import embedding_functions

from app.config import get_settings
from app.database import SessionLocal
from app.models import ClinicalDocument

logger = logging.getLogger("vector_store")
settings = get_settings()

_client = None
_collection = None

CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200


def get_collection():
    global _client, _collection
    if _collection is None:
        Path(settings.vector_db_dir).mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(path=settings.vector_db_dir)
        ef = embedding_functions.DefaultEmbeddingFunction()
        _collection = _client.get_or_create_collection(name="clinical_docs", embedding_function=ef)
    return _collection


def _chunk_text(text: str) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = start + CHUNK_SIZE
        chunks.append(text[start:end])
        start = end - CHUNK_OVERLAP
    return [c.strip() for c in chunks if c.strip()]


def _guess_title(first_page_text: str, fallback: str) -> str:
    for line in first_page_text.splitlines():
        line = line.strip()
        if len(line) > 15:
            return line[:200]
    return fallback


def index_pdf(pdf_path: Path) -> int:
    """Tek bir PDF'i indeksler, oluşturulan chunk sayısını döndürür."""
    collection = get_collection()
    filename = pdf_path.name

    collection.delete(where={"filename": filename})

    documents, metadatas, ids = [], [], []
    title = filename
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            page_text = page.extract_text() or ""
            if page_num == 1 and page_text:
                title = _guess_title(page_text, filename)
            for chunk_idx, chunk in enumerate(_chunk_text(page_text)):
                documents.append(chunk)
                metadatas.append({"filename": filename, "page": page_num, "title": title})
                ids.append(f"{filename}::{page_num}::{chunk_idx}")

    if documents:
        collection.add(documents=documents, metadatas=metadatas, ids=ids)

    db = SessionLocal()
    try:
        existing = db.query(ClinicalDocument).filter(ClinicalDocument.filename == filename).first()
        if not existing:
            existing = ClinicalDocument(filename=filename)
            db.add(existing)
        existing.title = title
        existing.num_chunks = len(documents)
        db.commit()
    finally:
        db.close()

    return len(documents)


def reindex_all() -> int:
    folder = Path(settings.clinical_docs_folder)
    folder.mkdir(parents=True, exist_ok=True)
    total = 0
    for pdf_file in folder.glob("*.pdf"):
        try:
            total += index_pdf(pdf_file)
        except Exception:
            logger.exception("Klinik çalışma indekslenemedi: %s", pdf_file.name)
    return total


def query_relevant_chunks(question: str, n_results: int = 5) -> list[dict]:
    collection = get_collection()
    if collection.count() == 0:
        return []
    results = collection.query(query_texts=[question], n_results=min(n_results, collection.count()))
    chunks = []
    for doc, meta, dist in zip(results["documents"][0], results["metadatas"][0], results["distances"][0]):
        chunks.append({"text": doc, "filename": meta["filename"], "page": meta["page"], "title": meta.get("title"), "distance": dist})
    return chunks

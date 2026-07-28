"""Klinik çalışma PDF'lerini parçalayıp yerel bir Chroma vektör veritabanında
indeksler. Embedding için chromadb'nin varsayılan (onnxruntime tabanlı,
tamamen yerel/ücretsiz) MiniLM modelini kullanır; harici bir API anahtarı
gerekmez."""

import logging
from datetime import datetime
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
    file_size = pdf_path.stat().st_size

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
        existing.file_size = file_size
        existing.indexed_at = datetime.utcnow()
        db.commit()
    finally:
        db.close()

    return len(documents)


def _already_indexed(db, pdf_path: Path) -> bool:
    """Aynı isim ve aynı boyutta, chunk'ları üretilmiş bir kayıt varsa dosya
    değişmemiş demektir."""
    doc = (
        db.query(ClinicalDocument)
        .filter(ClinicalDocument.filename == pdf_path.name)
        .first()
    )
    return bool(doc and doc.num_chunks > 0 and doc.file_size == pdf_path.stat().st_size)


def reindex_all(force: bool = False) -> int:
    """Klinik çalışma klasörünü indeksler.

    Varsayılan olarak zaten indekslenmiş ve değişmemiş dosyaları ATLAR: bu
    fonksiyon her uygulama açılışında çalışıyor ve her PDF'i yeniden
    gömmek (embedding) doküman sayısıyla doğru orantılı sürüyordu - birkaç
    yüz çalışmadan sonra açılış dakikalarca sürer, sunucu açılış zaman
    aşımına düşerdi. Vektörler kalıcı diskte durduğu için yeniden üretmeye
    zaten gerek yok.
    """
    folder = Path(settings.clinical_docs_folder)
    folder.mkdir(parents=True, exist_ok=True)

    db = SessionLocal()
    try:
        pending = [
            pdf for pdf in folder.glob("*.pdf")
            if force or not _already_indexed(db, pdf)
        ]
    finally:
        db.close()

    if not pending:
        return 0

    logger.info("İndekslenecek klinik çalışma sayısı: %d", len(pending))
    total = 0
    for pdf_file in pending:
        try:
            total += index_pdf(pdf_file)
        except Exception:
            logger.exception("Klinik çalışma indekslenemedi: %s", pdf_file.name)
    return total


def remove_document(filename: str) -> None:
    """Bir klinik çalışmanın vektörlerini indeksten siler."""
    get_collection().delete(where={"filename": filename})


def reset_client() -> None:
    """Bellekteki Chroma istemcisini serbest bırakır.

    Yedekten geri yükleme vektör dizinini diskte komple değiştiriyor; açık
    olan istemci o noktada artık var olmayan bir dizine bakar ve asistan
    sunucu yeniden başlatılana kadar bozuk kalırdı.

    Kendi değişkenlerimizi sıfırlamak yeterli DEĞİL: Chroma, istemcileri
    süreç içinde yola göre kendi önbelleğinde tutuyor, dolayısıyla yeni bir
    PersistentClient çağrısı yine eski (bozuk) örneği döndürür. Bu yüzden
    Chroma'nın kendi önbelleği de temizlenir.
    """
    global _client, _collection
    _client = None
    _collection = None
    try:
        from chromadb.api.client import SharedSystemClient

        SharedSystemClient.clear_system_cache()
    except Exception:
        logger.exception("Chroma istemci önbelleği temizlenemedi")


def query_relevant_chunks(question: str, n_results: int = 5) -> list[dict]:
    collection = get_collection()
    if collection.count() == 0:
        return []
    results = collection.query(query_texts=[question], n_results=min(n_results, collection.count()))
    chunks = []
    for doc, meta, dist in zip(results["documents"][0], results["metadatas"][0], results["distances"][0]):
        chunks.append({"text": doc, "filename": meta["filename"], "page": meta["page"], "title": meta.get("title"), "distance": dist})
    return chunks

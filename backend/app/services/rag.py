import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import ChatLog
from app.schemas import SourceOut
from app.services.pubmed import search_pubmed
from app.services.qwen_client import ask_qwen
from app.services.vector_store import query_relevant_chunks

logger = logging.getLogger("rag")
settings = get_settings()

REFUSAL_MARKER = "İLGİSİZ_SORU"
REFUSAL_MESSAGE = (
    "Bu soruyu yanıtlayamıyorum. Bu asistan yalnızca şirketimizin ürünleri, "
    "bu ürünlerle ilgili hastalıklar ve klinik literatür hakkındaki sorulara, "
    "elimizdeki klinik çalışmalara ve PubMed'deki yayınlara dayanarak cevap verir. "
    "Lütfen ürün veya hastalıkla ilgili bir soru sorun."
)

SYSTEM_PROMPT = f"""Sen bir tıbbi cihaz/ürün şirketinin saha çalışanlarına yardımcı olan bir klinik literatür asistanısın.

KURALLAR:
1. YALNIZCA şirketin ürünleri, bu ürünlerle ilgili tıbbi/klinik konular ve hastalıklar hakkındaki sorulara cevap ver.
2. Cevaplarını SADECE aşağıda sağlanan "KLİNİK ÇALIŞMA KAYNAKLARI" ve "PUBMED KAYNAKLARI" bölümlerindeki bilgilere dayandır. Kendi genel bilgini veya tahminini kullanma.
3. Verilen kaynaklarda soruyu cevaplayacak yeterli/ilgili bilgi yoksa, ya da soru ürün/hastalık/klinik konularla alakasızsa (örn. hava durumu, spor, günlük sohbet), cevap olarak SADECE şu metni yaz: {REFUSAL_MARKER}
4. Cevap verirken mutlaka kaynak göster. Klinik çalışmalardan alıntı yaparken [Kaynak: dosya adı, sayfa X] formatını, PubMed'den alıntı yaparken [PubMed PMID: xxxxx] formatını kullan.
5. Türkçe, net ve profesyonel bir dille cevap ver. Tıbbi tavsiye verme; literatürü özetle ve kaynak göster.
"""

PUBMED_QUERY_SYSTEM_PROMPT = (
    "Aşağıdaki Türkçe soruyu PubMed'de arama yapmak üzere İngilizce, kısa "
    "anahtar kelimelere çevir (2-6 kelime). SADECE anahtar kelimeleri yaz; "
    "açıklama, noktalama işareti veya tırnak ekleme. Soru tıbbi bir ürün/"
    "hastalık/klinik konu içermiyorsa boş bırak."
)


def _timed(timings: dict, label: str, fn):
    start = time.perf_counter()
    try:
        return fn()
    finally:
        timings[label] = round((time.perf_counter() - start) * 1000)


@lru_cache(maxsize=256)
def _cached_search_terms(question: str) -> str:
    return _pubmed_search_terms(question)


def _pubmed_search_terms(question: str) -> str:
    """PubMed İngilizce indekslendiği için Türkçe soru doğrudan arama
    terimi olarak kullanıldığında neredeyse hiç sonuç dönmüyor. Qwen ile
    kısa İngilizce anahtar kelimelere çevirip onu aratıyoruz."""
    try:
        # Çıktı birkaç kelime; sınır koymamak modelin uzun uzun açıklama
        # üretip beklemeyi uzatmasına yol açıyordu.
        terms = ask_qwen(
            PUBMED_QUERY_SYSTEM_PROMPT, question, temperature=0.0, max_tokens=32
        ).strip()
        return terms or question
    except Exception:
        logger.exception("PubMed arama terimi çevirisi başarısız oldu, orijinal soru kullanılacak")
        return question


def _build_context(chunks: list[dict], pubmed_results: list[dict]) -> str:
    parts = []
    if chunks:
        parts.append("KLİNİK ÇALIŞMA KAYNAKLARI:")
        for c in chunks:
            parts.append(f"[Kaynak: {c['filename']}, sayfa {c['page']}]\n{c['text']}")
    else:
        parts.append("KLİNİK ÇALIŞMA KAYNAKLARI: (yerel klasörde ilgili içerik bulunamadı)")

    if pubmed_results:
        parts.append("\nPUBMED KAYNAKLARI:")
        for p in pubmed_results:
            parts.append(
                f"[PubMed PMID: {p['pmid']}] {p['title']} - {p['authors']} ({p['journal']}, {p['year']})"
            )
    else:
        parts.append("\nPUBMED KAYNAKLARI: (ilgili yayın bulunamadı)")

    return "\n\n".join(parts)


def _gather_sources(question: str, timings: dict) -> tuple[list[dict], list[dict]]:
    """Yerel doküman araması ile PubMed aramasını EŞ ZAMANLI çalıştırır.

    İkisi birbirinden tamamen bağımsız ama sırayla çalıştırıldıklarında
    süreleri toplanıyordu. PubMed dalı ayrıca kendi içinde bir Qwen çevirisi
    + iki NCBI isteği barındırdığı için asıl bekleme oradaydı.
    """
    with ThreadPoolExecutor(max_workers=2) as pool:
        chunks_task = pool.submit(
            _timed, timings, "dokuman_arama_ms", lambda: query_relevant_chunks(question, n_results=5)
        )
        pubmed_task = pool.submit(
            _timed, timings, "pubmed_ms", lambda: search_pubmed(_cached_search_terms(question), max_results=5)
        )
        return chunks_task.result(), pubmed_task.result()


def answer_question(
    db: Session, question: str, user_id: int | None, timings: dict | None = None
) -> tuple[str, list[SourceOut], bool]:
    """timings verilirse her aşamanın süresi (ms) oraya yazılır; verilmese de
    ölçüm yapılır ve loga düşer - "asistan yavaş" şikâyetinde nerede
    beklendiğini tahmin etmemek için."""
    timings = timings if timings is not None else {}
    started = time.perf_counter()
    try:
        return _answer_question(db, question, user_id, timings)
    finally:
        # Erken dönüşlerde (kaynak yok / model hatası) de toplam süre yazılmalı.
        timings["toplam_ms"] = round((time.perf_counter() - started) * 1000)
        logger.info("Asistan yanıt süreleri: %s", timings)


def _answer_question(
    db: Session, question: str, user_id: int | None, timings: dict
) -> tuple[str, list[SourceOut], bool]:
    chunks, pubmed_results = _gather_sources(question, timings)

    if not chunks and not pubmed_results:
        _log(db, user_id, question, REFUSAL_MESSAGE, [], was_answered=False)
        return REFUSAL_MESSAGE, [], False

    context = _build_context(chunks, pubmed_results)
    user_prompt = f"SORU: {question}\n\n{context}"

    try:
        raw_answer = _timed(timings, "qwen_cevap_ms", lambda: ask_qwen(SYSTEM_PROMPT, user_prompt))
    except Exception:
        logger.exception("Qwen çağrısı başarısız oldu")
        error_message = (
            "Şu anda klinik asistan modeline ulaşılamıyor (Qwen servisi yapılandırılmamış veya "
            "erişilemez olabilir). Lütfen yöneticinizle iletişime geçin."
        )
        _log(db, user_id, question, error_message, [], was_answered=False)
        return error_message, [], False

    if REFUSAL_MARKER in raw_answer:
        _log(db, user_id, question, REFUSAL_MESSAGE, [], was_answered=False)
        return REFUSAL_MESSAGE, [], False

    if not raw_answer.strip():
        # Model boş içerik döndürdü. En olası sebep token bütçesinin bitmesi:
        # "düşünme" (thinking) modu açıkken muhakeme de üretilen token
        # sayısına dahil oluyor ve cevaba sıra gelmeden QWEN_MAX_TOKENS
        # tükenebiliyor. Boş baloncuk göstermek yerine sebebini söyle.
        logger.warning("Qwen boş cevap döndürdü (QWEN_MAX_TOKENS=%s yetersiz olabilir)", settings.qwen_max_tokens)
        empty_message = (
            "Model bu soru için boş bir cevap döndürdü. Cevap uzunluğu sınırı "
            "(QWEN_MAX_TOKENS) yetersiz olabilir. Lütfen yöneticinizle iletişime geçin."
        )
        _log(db, user_id, question, empty_message, [], was_answered=False)
        return empty_message, [], False

    sources = [
        SourceOut(type="document", title=c["title"] or c["filename"], detail=f"{c['filename']} - sayfa {c['page']}")
        for c in chunks
    ] + [
        SourceOut(type="pubmed", title=p["title"], detail=f"{p['journal']} ({p['year']}) - PMID {p['pmid']}", url=p["url"])
        for p in pubmed_results
    ]

    _log(db, user_id, question, raw_answer, sources, was_answered=True)
    return raw_answer, sources, True


def _log(db: Session, user_id: int | None, question: str, answer: str, sources: list[SourceOut], was_answered: bool) -> None:
    try:
        db.add(ChatLog(
            user_id=user_id,
            question=question,
            answer=answer,
            was_answered=was_answered,
            sources_json=json.dumps([s.model_dump() for s in sources], ensure_ascii=False),
        ))
        db.commit()
    except Exception:
        logger.exception("Sohbet kaydı tutulamadı")
        db.rollback()

import json
import logging

from sqlalchemy.orm import Session

from app.models import ChatLog
from app.schemas import SourceOut
from app.services.pubmed import search_pubmed
from app.services.qwen_client import ask_qwen
from app.services.vector_store import query_relevant_chunks

logger = logging.getLogger("rag")

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


def answer_question(db: Session, question: str, user_id: int | None) -> tuple[str, list[SourceOut], bool]:
    chunks = query_relevant_chunks(question, n_results=5)
    pubmed_results = search_pubmed(question, max_results=5)

    if not chunks and not pubmed_results:
        _log(db, user_id, question, REFUSAL_MESSAGE, [], was_answered=False)
        return REFUSAL_MESSAGE, [], False

    context = _build_context(chunks, pubmed_results)
    user_prompt = f"SORU: {question}\n\n{context}"

    try:
        raw_answer = ask_qwen(SYSTEM_PROMPT, user_prompt)
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

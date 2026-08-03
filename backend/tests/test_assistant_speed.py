"""Klinik asistanın hız davranışı.

Asistan soru başına dört ağ turu yapıyordu ve hepsi SIRAYLA çalışıyordu:
yerel vektör araması → Qwen (soruyu İngilizce anahtar kelimeye çevir) →
NCBI (esearch + esummary) → Qwen (asıl cevap). Buradaki testler ilk üçünün
artık paralelleştiğini ve ölçümün her yolda tutulduğunu kanıtlar.
"""

import time

import pytest

from app.services import rag


@pytest.fixture(autouse=True)
def clear_term_cache():
    rag._cached_search_terms.cache_clear()
    yield
    rag._cached_search_terms.cache_clear()


def _stub(monkeypatch, *, doc_delay=0.0, pubmed_delay=0.0, qwen_delay=0.0, chunks=None, articles=None):
    def fake_chunks(question, n_results=5):
        time.sleep(doc_delay)
        return chunks if chunks is not None else [
            {"text": "içerik", "filename": "c.pdf", "page": 1, "title": "Çalışma", "distance": 0.1}
        ]

    def fake_pubmed(query, max_results=5):
        time.sleep(pubmed_delay)
        return articles if articles is not None else [
            {"pmid": "1", "title": "T", "journal": "J", "year": "2024", "authors": "A", "url": "u"}
        ]

    def fake_qwen(system_prompt, user_prompt, temperature=0.2, max_tokens=None, meta=None):
        time.sleep(qwen_delay)
        if system_prompt is rag.PUBMED_QUERY_SYSTEM_PROMPT:
            return "aspirin cardiovascular\nantiplatelet therapy"
        return "Cevap [Kaynak: c.pdf, sayfa 1]"

    monkeypatch.setattr(rag, "query_relevant_chunks", fake_chunks)
    monkeypatch.setattr(rag, "search_pubmed", fake_pubmed)
    monkeypatch.setattr(rag, "ask_qwen", fake_qwen)


def test_timings_cover_every_stage(client, admin, monkeypatch):
    _stub(monkeypatch)
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        timings = {}
        answer, sources, was_answered = rag.answer_question(db, "aspirin faydası", None, timings)
    finally:
        db.close()

    assert was_answered
    assert len(sources) == 2  # bir doküman + bir PubMed kaynağı
    assert {k for k in timings if k.endswith("_ms")} == {
        "ceviri_ms", "dokuman_arama_ms", "pubmed_ms", "qwen_cevap_ms", "toplam_ms"
    }
    # Kaynak sayıları, uzaklıklar ve PubMed'e giden İngilizce sorgu da kaydedilmeli.
    assert timings["dokuman_parca_sayisi"] == 1
    assert timings["pubmed_sonuc_sayisi"] == 1
    assert timings["pubmed_sorgusu"] == "aspirin cardiovascular"
    assert timings["en_yakin_dokuman_uzakligi"] == 0.1


def test_document_search_and_pubmed_run_in_parallel(monkeypatch):
    """İkisi birbirinden bağımsız; sırayla çalıştırıldıklarında süreleri
    toplanıyordu."""
    _stub(monkeypatch, doc_delay=0.3, pubmed_delay=0.3)
    timings = {}
    rag._gather_sources("soru", timings)

    started = time.perf_counter()
    rag._cached_search_terms.cache_clear()
    rag._gather_sources("başka soru", timings)
    elapsed = time.perf_counter() - started

    # Seri çalışsaydı en az 0.6 sn sürerdi.
    assert elapsed < 0.5, elapsed


def test_pubmed_translation_is_cached(monkeypatch):
    calls = []

    def counting_qwen(system_prompt, user_prompt, temperature=0.2, max_tokens=None):
        calls.append(system_prompt)
        return "aspirin\nantiplatelet"

    monkeypatch.setattr(rag, "ask_qwen", counting_qwen)
    assert rag._cached_search_terms("aynı soru") == ("aspirin", "antiplatelet")
    rag._cached_search_terms("aynı soru")
    assert len(calls) == 1  # aynı soru ikinci kez modele gitmemeli


def test_falls_back_to_broader_query_when_specific_one_finds_nothing(monkeypatch):
    """PubMed VE mantığıyla arıyor ve ticari marka adlarını indekslemiyor;
    "Efferon Neo SOFA score" gibi dar bir sorgu sıfır sonuç döndürüyordu."""
    searched = []

    def fake_search(query, max_results=5):
        searched.append(query)
        # Marka adı içeren dar sorgu boş, mekanizma düzeyindeki sorgu dolu.
        return [] if "Efferon" in query else [
            {"pmid": "9", "title": "T", "journal": "J", "year": "2024", "authors": "A", "url": "u"}
        ]

    monkeypatch.setattr(rag, "search_pubmed", fake_search)
    monkeypatch.setattr(rag, "query_relevant_chunks", lambda q, n_results=5: [])
    monkeypatch.setattr(
        rag, "ask_qwen", lambda *a, **k: "Efferon Neo SOFA score\nhemoperfusion sepsis"
    )

    timings = {}
    _, pubmed_results = rag._gather_sources("efferon neo sofa skorunu düşürür mü", timings)

    assert searched == ["Efferon Neo SOFA score", "hemoperfusion sepsis"]
    assert len(pubmed_results) == 1
    assert timings["pubmed_genel_sorgu"] == "hemoperfusion sepsis"


def test_irrelevant_chunks_are_dropped_by_the_distance_threshold(monkeypatch):
    """Canlı ölçüm: konusu kapsanan soruda en yakın parça 0.595, kapsanmayan
    soruda 1.142. Eşik ikisinin arasında; uzak parçalar bağlama girmemeli."""
    from app.config import get_settings

    limit = get_settings().document_max_distance
    far = [
        {"text": "x", "filename": "f.pdf", "page": 1, "title": "T", "distance": limit + 0.2}
        for _ in range(5)
    ]
    monkeypatch.setattr(rag, "query_relevant_chunks", lambda q, n_results=5: far)
    monkeypatch.setattr(rag, "search_pubmed", lambda q, max_results=5: [])
    monkeypatch.setattr(rag, "ask_qwen", lambda *a, **k: "terms\nbroad")

    timings = {}
    chunks, _ = rag._gather_sources("alakasız soru", timings)

    assert chunks == []
    assert timings["dokuman_parca_sayisi"] == 0
    assert timings["elenen_parca_sayisi"] == 5
    # Uzaklıklar elemeden ÖNCE kaydedilmeli, yoksa eşik ayarlanamaz.
    assert timings["en_yakin_dokuman_uzakligi"] == round(limit + 0.2, 3)


def test_relevant_chunks_survive_the_threshold(monkeypatch):
    from app.config import get_settings

    limit = get_settings().document_max_distance
    near = [{"text": "x", "filename": "f.pdf", "page": 1, "title": "T", "distance": limit - 0.3}]
    monkeypatch.setattr(rag, "query_relevant_chunks", lambda q, n_results=5: near)
    monkeypatch.setattr(rag, "search_pubmed", lambda q, max_results=5: [])
    monkeypatch.setattr(rag, "ask_qwen", lambda *a, **k: "terms\nbroad")

    timings = {}
    chunks, _ = rag._gather_sources("kapsanan soru", timings)

    assert len(chunks) == 1
    assert "elenen_parca_sayisi" not in timings


def test_no_model_call_when_everything_is_filtered_out(monkeypatch):
    """Eşiğin asıl kazancı: ilgisiz soruda Qwen hiç çağrılmamalı. Eskiden
    ilgisiz 5 parça modele gidiyor, model reddediyor ve bu 8-14 saniye
    sürüyordu."""
    from app.config import get_settings
    from app.database import SessionLocal

    limit = get_settings().document_max_distance
    far = [{"text": "x", "filename": "f.pdf", "page": 1, "title": "T", "distance": limit + 0.5}]
    monkeypatch.setattr(rag, "query_relevant_chunks", lambda q, n_results=5: far)
    monkeypatch.setattr(rag, "search_pubmed", lambda q, max_results=5: [])

    qwen_calls = []

    def counting_qwen(system_prompt, user_prompt, temperature=0.2, max_tokens=None):
        qwen_calls.append(system_prompt)
        return "terms\nbroad"

    monkeypatch.setattr(rag, "ask_qwen", counting_qwen)

    db = SessionLocal()
    try:
        timings = {}
        _, _, was_answered = rag.answer_question(db, "alakasız soru", None, timings)
    finally:
        db.close()

    assert not was_answered
    assert qwen_calls == [rag.PUBMED_QUERY_SYSTEM_PROMPT]  # sadece çeviri, cevap çağrısı yok
    assert "qwen_cevap_ms" not in timings


def test_document_search_uses_the_english_translation(monkeypatch):
    """Embedding modeli (MiniLM) yalnızca İngilizce: Türkçe soruyla aratınca
    ilgili dokümana olan uzaklık, alakasız bir sorununkiyle aynı çıkıyordu.
    PubMed için zaten ürettiğimiz çeviri vektör aramasında da kullanılmalı."""
    searched = []
    monkeypatch.setattr(
        rag, "query_relevant_chunks", lambda q, n_results=5: searched.append(q) or []
    )
    monkeypatch.setattr(rag, "search_pubmed", lambda q, max_results=5: [])
    monkeypatch.setattr(rag, "ask_qwen", lambda *a, **k: "septic shock complications\nsepsis")

    timings = {}
    rag._gather_sources("septik şokun sebep olduğu problemler nelerdir", timings)

    assert searched == ["septic shock complications"]
    assert timings["dokuman_sorgusu"] == "septic shock complications"


def test_document_search_falls_back_to_turkish_when_translation_fails(monkeypatch):
    """Çeviri koparsa arama yine yapılmalı - eskisinden kötü olmamalı."""
    searched = []
    monkeypatch.setattr(
        rag, "query_relevant_chunks", lambda q, n_results=5: searched.append(q) or []
    )
    monkeypatch.setattr(rag, "search_pubmed", lambda q, max_results=5: [])

    def broken_qwen(*a, **k):
        raise RuntimeError("model ulaşılamıyor")

    monkeypatch.setattr(rag, "ask_qwen", broken_qwen)

    rag._gather_sources("septik şok soru", {})
    assert searched == ["septik şok soru"]


def test_no_second_pubmed_call_when_specific_query_succeeds(monkeypatch):
    """Yedek sorgu ekstra bir NCBI turu demek; ilki sonuç verdiyse yapılmamalı."""
    searched = []

    def fake_search(query, max_results=5):
        searched.append(query)
        return [{"pmid": "1", "title": "T", "journal": "J", "year": "2024", "authors": "A", "url": "u"}]

    monkeypatch.setattr(rag, "search_pubmed", fake_search)
    monkeypatch.setattr(rag, "query_relevant_chunks", lambda q, n_results=5: [])
    monkeypatch.setattr(rag, "ask_qwen", lambda *a, **k: "aspirin cardiovascular\nantiplatelet")

    timings = {}
    rag._gather_sources("aspirin sorusu", timings)

    assert searched == ["aspirin cardiovascular"]
    assert "pubmed_genel_sorgu" not in timings


def test_total_time_recorded_even_when_no_sources(monkeypatch):
    """Erken dönüşlerde de ölçüm tutulmalı - yoksa 'kaynak bulunamadı'
    yanıtlarının neden yavaş olduğu görünmez."""
    _stub(monkeypatch, chunks=[], articles=[])
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        timings = {}
        answer, _, was_answered = rag.answer_question(db, "hava durumu", None, timings)
    finally:
        db.close()

    assert not was_answered
    assert "toplam_ms" in timings
    assert "qwen_cevap_ms" not in timings  # kaynak yoksa model hiç çağrılmamalı
    # "Yanlış soru sordunuz" değil, "bu konuda kaynağım yok" denmeli.
    assert answer == rag.NO_SOURCES_MESSAGE


def test_answers_when_sources_are_related_but_incomplete(monkeypatch):
    """Canlı ölçümde en yakın parça 0.594 (belirgin ilgili) olduğu halde model
    reddediyordu: soruyu birebir cevaplamayan ama konuyla ilgili kaynakları
    "yetersiz" sayıyordu. Kaynaklı eksik cevap, hiç cevap vermemekten iyi."""
    _stub(monkeypatch)
    partial = (
        "Kaynaklarda ameliyat süresine dair doğrudan bir karşılaştırma yok; "
        "bildirilen sonuçlar şunlardır [Kaynak: c.pdf, sayfa 1]"
    )
    monkeypatch.setattr(
        rag,
        "ask_qwen",
        lambda system_prompt, *a, **k: (
            "aspirin cardiovascular\nantiplatelet"
            if system_prompt is rag.PUBMED_QUERY_SYSTEM_PROMPT
            else partial
        ),
    )
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        answer, sources, was_answered = rag.answer_question(db, "soru", None, {})
    finally:
        db.close()

    assert was_answered
    assert answer == partial
    assert len(sources) == 2


def test_truncated_answer_is_marked_not_passed_off_as_complete(monkeypatch):
    """Uzunluk sınırına takılan cevap cümlenin ortasında bitiyor; klinik bir
    metnin yarım kaldığı anlaşılmazsa eksik bilgi tam sanılır."""
    _stub(monkeypatch)

    def truncating_qwen(system_prompt, user_prompt, temperature=0.2, max_tokens=None, meta=None):
        if system_prompt is rag.PUBMED_QUERY_SYSTEM_PROMPT:
            return "aspirin cardiovascular\nantiplatelet"
        if meta is not None:
            meta["finish_reason"] = "length"
        return "Efferon LPS septik şokta mortaliteyi azaltır ve hemodinamik stabil"

    monkeypatch.setattr(rag, "ask_qwen", truncating_qwen)
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        timings = {}
        answer, _, was_answered = rag.answer_question(db, "soru", None, timings)
    finally:
        db.close()

    assert was_answered  # eldeki kısmi cevap yine gösterilmeli
    assert "tamamlanamadı" in answer
    assert timings["cevap_kesildi"] is True


def test_complete_answer_is_not_marked_as_truncated(monkeypatch):
    _stub(monkeypatch)
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        timings = {}
        answer, _, _ = rag.answer_question(db, "soru", None, timings)
    finally:
        db.close()

    assert "tamamlanamadı" not in answer
    assert "cevap_kesildi" not in timings


def test_empty_model_output_is_reported_not_shown_blank(monkeypatch):
    """qwen-plus gibi "düşünme" modu olan modellerde muhakeme de token
    bütçesinden yeniyor; bütçe cevaba sıra gelmeden bitince model boş içerik
    döndürüyor ve kullanıcı boş bir baloncuk görüyordu."""
    _stub(monkeypatch)
    monkeypatch.setattr(rag, "ask_qwen", lambda *a, **k: "   ")
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        answer, _, was_answered = rag.answer_question(db, "aspirin", None, {})
    finally:
        db.close()

    assert not was_answered
    assert "QWEN_MAX_TOKENS" in answer


def test_timing_diagnostics_endpoint_is_admin_only(client, admin, employee, monkeypatch):
    _stub(monkeypatch)
    assert client.post("/assistant/timing-diagnostics", json={"question": "s"}, headers=employee).status_code == 403

    r = client.post("/assistant/timing-diagnostics", json={"question": "aspirin"}, headers=admin)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["was_answered"] is True
    assert body["source_count"] == 2
    assert body["timings_ms"]["toplam_ms"] >= 0
    assert all(k.endswith("_ms") for k in body["timings_ms"])
    assert body["kaynaklar"]["dokuman_parca_sayisi"] == 1
    assert body["kaynaklar"]["pubmed_sonuc_sayisi"] == 1
    assert "model" in body

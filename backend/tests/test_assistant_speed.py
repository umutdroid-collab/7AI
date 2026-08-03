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

    def fake_qwen(system_prompt, user_prompt, temperature=0.2, max_tokens=None):
        time.sleep(qwen_delay)
        if system_prompt is rag.PUBMED_QUERY_SYSTEM_PROMPT:
            return "aspirin cardiovascular"
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
    assert set(timings) == {"dokuman_arama_ms", "pubmed_ms", "qwen_cevap_ms", "toplam_ms"}


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
        return "aspirin"

    monkeypatch.setattr(rag, "ask_qwen", counting_qwen)
    rag._cached_search_terms("aynı soru")
    rag._cached_search_terms("aynı soru")
    assert len(calls) == 1  # aynı soru ikinci kez modele gitmemeli


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


def test_timing_diagnostics_endpoint_is_admin_only(client, admin, employee, monkeypatch):
    _stub(monkeypatch)
    assert client.post("/assistant/timing-diagnostics", json={"question": "s"}, headers=employee).status_code == 403

    r = client.post("/assistant/timing-diagnostics", json={"question": "aspirin"}, headers=admin)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["was_answered"] is True
    assert body["source_count"] == 2
    assert body["timings_ms"]["toplam_ms"] >= 0
    assert "model" in body

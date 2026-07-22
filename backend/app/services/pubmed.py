"""NCBI E-utilities üzerinden PubMed araması. Sorunun ürün/hastalık konusuyla
ilgili güncel literatürde bir karşılığı var mı diye bakmak için kullanılır."""

import logging

import requests

from app.config import get_settings

logger = logging.getLogger("pubmed")
settings = get_settings()

ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"


def _common_params() -> dict:
    params = {"retmode": "json", "tool": "7ai-clinical-assistant"}
    if settings.pubmed_email:
        params["email"] = settings.pubmed_email
    if settings.pubmed_api_key:
        params["api_key"] = settings.pubmed_api_key
    return params


def search_pubmed(query: str, max_results: int = 5) -> list[dict]:
    try:
        search_resp = requests.get(
            ESEARCH_URL,
            params={**_common_params(), "db": "pubmed", "term": query, "retmax": max_results, "sort": "relevance"},
            timeout=10,
        )
        search_resp.raise_for_status()
        ids = search_resp.json().get("esearchresult", {}).get("idlist", [])
        if not ids:
            return []

        summary_resp = requests.get(
            ESUMMARY_URL,
            params={**_common_params(), "db": "pubmed", "id": ",".join(ids)},
            timeout=10,
        )
        summary_resp.raise_for_status()
        summary = summary_resp.json().get("result", {})

        articles = []
        for pmid in ids:
            item = summary.get(pmid)
            if not item:
                continue
            authors = ", ".join(a.get("name", "") for a in item.get("authors", [])[:3])
            articles.append({
                "pmid": pmid,
                "title": item.get("title", "").strip(),
                "journal": item.get("fulljournalname") or item.get("source"),
                "year": (item.get("pubdate") or "")[:4],
                "authors": authors,
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            })
        return articles
    except requests.RequestException:
        logger.exception("PubMed araması başarısız oldu")
        return []

"""EvoBulut (e-fatura kesim yazılımı) API entegrasyonu - satış faturalarını
otomatik çekip Fatura Takip sistemine aktarmak için kullanılır.

API dokümantasyonu: https://dev.evobulut.com/ - tek bir endpoint üzerinden
"cmd" parametresiyle yönlendirilen bir yapı. Önce kullanıcı kodu/şifre ile
giriş yapılıp bir token (UID) alınıyor, sonraki tüm isteklerde bu token
hem body'de hem X-ClientId header'ında gönderiliyor."""

import logging
import threading

import requests

from app.config import get_settings

logger = logging.getLogger("evobulut")
settings = get_settings()

BASE_URL = "https://ws.evobulut.com/api"

_token_lock = threading.Lock()
_cached_token: str | None = None


class EvoBulutError(Exception):
    pass


def _login() -> str:
    if not settings.evobulut_username or not settings.evobulut_password:
        raise EvoBulutError("EVOBULUT_USERNAME / EVOBULUT_PASSWORD ayarlanmamış")

    resp = requests.post(
        f"{BASE_URL}/index/base/",
        json={
            "cmd": "euas",
            "p1": settings.evobulut_username,
            "p2": settings.evobulut_password,
            "app": settings.evobulut_app_name,
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "OK":
        raise EvoBulutError(f"Giriş başarısız: {data}")

    ana = data.get("veri", {}).get("Ana", [])
    if not ana or not ana[0].get("UID"):
        raise EvoBulutError(f"Giriş yanıtında token (UID) bulunamadı: {data}")
    return ana[0]["UID"]


def _get_token(force_refresh: bool = False) -> str:
    global _cached_token
    with _token_lock:
        if _cached_token is None or force_refresh:
            _cached_token = _login()
        return _cached_token


def _call(module_path: str, payload: dict, retry: bool = True) -> dict:
    """module_path örn. 'fatura'. Token süresi dolmuşsa bir kez yeniden giriş
    yapıp tekrar dener."""
    token = _get_token()
    body = {"UID": token, **payload}
    resp = requests.post(
        f"{BASE_URL}/{module_path}/base/",
        json=body,
        headers={"X-ClientId": token},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "OK":
        if retry:
            _get_token(force_refresh=True)
            return _call(module_path, payload, retry=False)
        raise EvoBulutError(f"EvoBulut hata döndürdü: {data}")
    return data


def fetch_sales_invoices(tarih_bas: str = "", tarih_son: str = "", sayfa: int = 0, a_onay: str = "") -> list[dict]:
    """Satış faturalarını (tur=31) çeker. tarih_bas/tarih_son "DD.MM.YYYY" formatında.
    a_onay="1" sadece onaylı faturaları getirir."""
    data = _call("fatura", {
        "cmd": "jq_list",
        "sayfa": str(sayfa),
        "a_onay": a_onay,
        "a_cari_id": "",
        "a_tarih_bas": tarih_bas,
        "a_tarih_son": tarih_son,
        "a_stok_id": "",
        "a_stok_ack": "",
        "ara": "",
        "tur": "31",
    })
    return data.get("veri", {}).get("Ana", [])


PAGE_SIZE = 30
MAX_PAGES = 100


def fetch_all_sales_invoices(a_onay: str = "1") -> list[dict]:
    """jq_list sayfalama yapıyor (sayfa başına 30 kayıt); boş/eksik bir sayfa
    gelene kadar tüm sayfaları çeker."""
    all_items: list[dict] = []
    for sayfa in range(MAX_PAGES):
        items = fetch_sales_invoices(sayfa=sayfa, a_onay=a_onay)
        all_items.extend(items)
        if len(items) < PAGE_SIZE:
            break
    return all_items


def fetch_invoice_pdf_url(evobulut_id: str) -> str | None:
    """eFaturaPdfGetir, PDF'in kendisini değil onu indirebileceğimiz bir
    URL döner (veri[0].mesaj)."""
    data = _call("fatura", {"cmd": "eFaturaPdfGetir", "a_id": evobulut_id})
    veri = data.get("veri")
    if isinstance(veri, list) and veri and veri[0].get("mesaj"):
        return veri[0]["mesaj"]
    return None


def download_pdf_bytes(url: str) -> bytes:
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.content

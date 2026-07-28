"""E-posta gönderimi. Vade ve SKT uyarıları şimdiye kadar sadece uygulama
içindeki zilde görünüyordu; kimse uygulamayı açmazsa uyarı kimseye
ulaşmıyordu. Günlük özet e-postası bu boşluğu kapatır.

İki gönderim yolu desteklenir:

1. Resend (HTTPS API) - varsayılan. Railway'in Hobby planı giden SMTP
   portlarını (25/465/587/2525) tamamen engellediği için bulutta tek
   çalışan yöntem budur.
2. SMTP - SMTP'nin açık olduğu ortamlar (kendi sunucusu, Railway Pro vb.)
   için yedek yol.
"""

import logging
import smtplib
from email.message import EmailMessage

import requests

from app.config import get_settings

logger = logging.getLogger("email")
settings = get_settings()

RESEND_URL = "https://api.resend.com/emails"
SMTP_TIMEOUT_SECONDS = 15


class EmailNotConfigured(Exception):
    pass


def is_configured() -> bool:
    if not settings.smtp_from:
        return False
    return bool(settings.resend_api_key or settings.smtp_host)


def provider_name() -> str:
    if settings.resend_api_key:
        return "resend"
    if settings.smtp_host:
        return "smtp"
    return "none"


def _send_via_resend(to: list[str], subject: str, html_body: str, text_body: str) -> None:
    response = requests.post(
        RESEND_URL,
        headers={"Authorization": f"Bearer {settings.resend_api_key}"},
        json={
            # Alıcılar birbirinin adresini görmesin diye asıl adresler bcc'ye
            # konur; "to" zorunlu olduğundan gönderen adresi yazılır.
            "from": settings.smtp_from,
            "to": [settings.smtp_from],
            "bcc": to,
            "subject": subject,
            "html": html_body,
            "text": text_body,
        },
        timeout=30,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"Resend hatası (HTTP {response.status_code}): {response.text}")


def _send_via_smtp(to: list[str], subject: str, html_body: str, text_body: str) -> None:
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.smtp_from
    message["To"] = settings.smtp_from
    message["Bcc"] = ", ".join(to)
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=SMTP_TIMEOUT_SECONDS) as server:
        if settings.smtp_use_tls:
            server.starttls()
        if settings.smtp_username:
            server.login(settings.smtp_username, settings.smtp_password)
        server.send_message(message)


def send_email(to: list[str], subject: str, html_body: str, text_body: str) -> None:
    """Tek bir e-postayı verilen alıcılara gönderir."""
    if not is_configured():
        raise EmailNotConfigured(
            "E-posta ayarları eksik. SMTP_FROM ile birlikte RESEND_API_KEY "
            "(önerilen) veya SMTP_HOST tanımlanmalı."
        )
    if not to:
        return

    provider = provider_name()
    if provider == "resend":
        _send_via_resend(to, subject, html_body, text_body)
    else:
        _send_via_smtp(to, subject, html_body, text_body)

    logger.info("E-posta gönderildi (%s): '%s' -> %d alıcı", provider, subject, len(to))

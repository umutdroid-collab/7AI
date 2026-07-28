"""SMTP üzerinden e-posta gönderimi. Vade ve SKT uyarıları şimdiye kadar
sadece uygulama içindeki zilde görünüyordu; kimse uygulamayı açmazsa uyarı
kimseye ulaşmıyordu. Günlük özet e-postası bu boşluğu kapatır.

Standart kütüphanenin smtplib'i kullanılıyor - ek bir bağımlılık gerekmiyor."""

import logging
import smtplib
from email.message import EmailMessage

from app.config import get_settings

logger = logging.getLogger("email")
settings = get_settings()


class EmailNotConfigured(Exception):
    pass


def is_configured() -> bool:
    return bool(settings.smtp_host and settings.smtp_from)


def send_email(to: list[str], subject: str, html_body: str, text_body: str) -> None:
    """Tek bir e-postayı verilen alıcılara gönderir. Alıcılar birbirini
    görmesin diye adresler Bcc'ye konur."""
    if not is_configured():
        raise EmailNotConfigured(
            "SMTP ayarları eksik (SMTP_HOST ve SMTP_FROM tanımlanmalı)"
        )
    if not to:
        return

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.smtp_from
    message["To"] = settings.smtp_from
    message["Bcc"] = ", ".join(to)
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as server:
        if settings.smtp_use_tls:
            server.starttls()
        if settings.smtp_username:
            server.login(settings.smtp_username, settings.smtp_password)
        server.send_message(message)

    logger.info("E-posta gönderildi: '%s' -> %d alıcı", subject, len(to))

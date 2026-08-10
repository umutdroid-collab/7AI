"""Günlük vade/SKT özeti e-postası. Her sabah, o gün ilgilenilmesi gereken
kalemleri (vadesi geçmiş/yaklaşan faturalar, SKT'si yaklaşan stoklar) tek bir
e-postada toplar.

Bildirim (Notification) kayıtları yerine canlı sorgu kullanılıyor: özet
"bugün ne yapılmalı" anlık görüntüsü olmalı, bildirim okundu/okunmadı
defterinden bağımsız.
"""

import logging
from datetime import date, timedelta

from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.database import SessionLocal
from app.models import FollowUp, Invoice, InvoiceStatus, StockItem, StockItemStatus, User
from app.services.email import EmailNotConfigured, is_configured, send_email

logger = logging.getLogger("daily_digest")
settings = get_settings()

ACTIVE_STOCK_STATUSES = [
    StockItemStatus.IN_STOCK,
    StockItemStatus.AT_HOSPITAL,
    StockItemStatus.IN_VEHICLE,
]


def _money(invoice: Invoice) -> str:
    if invoice.amount is None:
        return "tutar bilinmiyor"
    return f"{invoice.amount:,.2f} {invoice.currency}".replace(",", "X").replace(".", ",").replace("X", ".")


def _invoice_label(invoice: Invoice) -> str:
    return invoice.invoice_number or invoice.source_filename


def collect_digest(db: Session) -> dict:
    today = date.today()
    upcoming_cutoff = today + timedelta(days=settings.invoice_reminder_days)
    skt_cutoff = today + timedelta(days=settings.skt_warning_days)

    unpaid = [
        Invoice.due_date.isnot(None),
        Invoice.status != InvoiceStatus.PAID,
    ]

    overdue = (
        db.query(Invoice)
        .filter(*unpaid, Invoice.due_date < today)
        .order_by(Invoice.due_date)
        .all()
    )
    upcoming = (
        db.query(Invoice)
        .filter(*unpaid, Invoice.due_date >= today, Invoice.due_date <= upcoming_cutoff)
        .order_by(Invoice.due_date)
        .all()
    )
    expiring = (
        db.query(StockItem)
        .options(joinedload(StockItem.product), joinedload(StockItem.hospital))
        .filter(StockItem.skt <= skt_cutoff, StockItem.status.in_(ACTIVE_STOCK_STATUSES))
        .order_by(StockItem.skt)
        .all()
    )

    # Tarihi gelmiş (ya da geçmiş) takip notları. Notun amacı zaten
    # "unutmayayım" olduğu için hatırlatma tam da burada yapılmalı.
    due_follow_ups = (
        db.query(FollowUp)
        .options(joinedload(FollowUp.about_user), joinedload(FollowUp.checkin))
        .filter(FollowUp.is_done.is_(False), FollowUp.remind_on <= today)
        .order_by(FollowUp.remind_on)
        .all()
    )

    return {
        "today": today,
        "overdue": overdue,
        "upcoming": upcoming,
        "expiring": expiring,
        "follow_ups": due_follow_ups,
    }


def _render(digest: dict) -> tuple[str, str, str]:
    """(konu, html, düz metin) döner."""
    today: date = digest["today"]
    overdue: list[Invoice] = digest["overdue"]
    upcoming: list[Invoice] = digest["upcoming"]
    expiring: list[StockItem] = digest["expiring"]
    follow_ups: list[FollowUp] = digest["follow_ups"]

    headline_parts = []
    if follow_ups:
        headline_parts.append(f"{len(follow_ups)} hatırlatıcı")
    if overdue:
        headline_parts.append(f"{len(overdue)} vadesi geçmiş fatura")
    if upcoming:
        headline_parts.append(f"{len(upcoming)} yaklaşan vade")
    if expiring:
        headline_parts.append(f"{len(expiring)} SKT uyarısı")
    subject = f"7AI Günlük Özet - {' , '.join(headline_parts)}"

    text_lines = [f"7AI Günlük Özet ({today.strftime('%d.%m.%Y')})", ""]
    html_sections = []

    def add_section(title: str, color: str, rows: list[tuple[str, str]]) -> None:
        if not rows:
            return
        text_lines.append(f"{title} ({len(rows)})")
        for main, detail in rows:
            text_lines.append(f"  - {main} | {detail}")
        text_lines.append("")

        row_html = "".join(
            f'<tr><td style="padding:8px 12px;border-bottom:1px solid #e5e7eb;">'
            f'<div style="font-weight:600;color:#0f172a;">{main}</div>'
            f'<div style="font-size:13px;color:#64748b;">{detail}</div></td></tr>'
            for main, detail in rows
        )
        html_sections.append(
            f'<h3 style="margin:24px 0 8px;color:{color};font-size:16px;">{title} ({len(rows)})</h3>'
            f'<table style="width:100%;border-collapse:collapse;background:#fff;'
            f'border:1px solid #e5e7eb;border-radius:8px;">{row_html}</table>'
        )

    # Hatırlatıcılar en üstte: yöneticinin kendi eliyle "bunu unutma" dediği
    # kalemler, otomatik üretilen uyarılardan önce gelmeli.
    add_section(
        "Hatırlatıcılar",
        "#7c3aed",
        [
            (
                f.note,
                " - ".join(
                    part
                    for part in [
                        f.about_user.full_name if f.about_user else None,
                        f.checkin.hospital.name if f.checkin else None,
                        (
                            f"{(today - f.remind_on).days} gün önceydi"
                            if f.remind_on < today
                            else "bugün"
                        ),
                    ]
                    if part
                ),
            )
            for f in follow_ups
        ],
    )
    add_section(
        "Vadesi Geçmiş Faturalar",
        "#dc2626",
        [
            (
                _invoice_label(i),
                f"{i.counterparty or 'Tedarikçi bilgisi yok'} - {_money(i)} - "
                f"vade {i.due_date.strftime('%d.%m.%Y')} ({(today - i.due_date).days} gün gecikti)",
            )
            for i in overdue
        ],
    )
    add_section(
        "Vadesi Yaklaşan Faturalar",
        "#d97706",
        [
            (
                _invoice_label(i),
                f"{i.counterparty or 'Tedarikçi bilgisi yok'} - {_money(i)} - "
                f"vade {i.due_date.strftime('%d.%m.%Y')} ({(i.due_date - today).days} gün kaldı)",
            )
            for i in upcoming
        ],
    )
    add_section(
        "SKT'si Yaklaşan / Geçmiş Stoklar",
        "#0369a1",
        [
            (
                f"{s.product.name} (Lot {s.lot_no})",
                f"Ref {s.product.reference_no} - "
                f"{s.hospital.name if s.hospital else (s.carried_by.full_name + ' (araçta)' if s.carried_by else 'Depo')} - "
                f"SKT {s.skt.strftime('%d.%m.%Y')} "
                + (
                    f"({(today - s.skt).days} gün geçti)"
                    if s.skt < today
                    else f"({(s.skt - today).days} gün kaldı)"
                ),
            )
            for s in expiring
        ],
    )

    html = (
        '<div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;'
        'background:#f8fafc;padding:24px;color:#0f172a;">'
        '<div style="max-width:640px;margin:0 auto;">'
        f'<h2 style="margin:0 0 4px;font-size:20px;">7AI Günlük Özet</h2>'
        f'<div style="color:#64748b;font-size:14px;">{today.strftime("%d.%m.%Y")}</div>'
        f'{"".join(html_sections)}'
        f'<p style="margin-top:28px;"><a href="{settings.app_public_url}" '
        'style="background:#0284c7;color:#fff;text-decoration:none;padding:10px 18px;'
        'border-radius:8px;display:inline-block;font-weight:600;">Uygulamayı Aç</a></p>'
        '<p style="color:#94a3b8;font-size:12px;margin-top:24px;">'
        'Bu e-postayı almak istemiyorsanız uygulamadaki Profil ekranından '
        'e-posta bildirimlerini kapatabilirsiniz.</p>'
        "</div></div>"
    )

    text_lines.append(f"Uygulama: {settings.app_public_url}")
    return subject, html, "\n".join(text_lines)


def recipients(db: Session) -> list[str]:
    """E-posta bildirimini kapatmamış aktif kullanıcılar. NULL, migrasyonla
    sonradan eklenen sütunda 'henüz seçim yapılmadı' demek - varsayılan açık."""
    users = (
        db.query(User)
        .filter(User.is_active.is_(True), User.email_notifications_enabled.isnot(False))
        .all()
    )
    return [u.email for u in users if u.email]


def send_daily_digest() -> dict:
    if not is_configured():
        logger.info("E-posta ayarlanmamış, günlük özet atlandı")
        return {
            "ok": False,
            "message": "E-posta ayarlanmamış (RESEND_API_KEY veya SMTP_HOST ile SMTP_FROM gerekli)",
        }

    db = SessionLocal()
    try:
        digest = collect_digest(db)
        total = (
            len(digest["overdue"])
            + len(digest["upcoming"])
            + len(digest["expiring"])
            + len(digest["follow_ups"])
        )
        if total == 0:
            logger.info("Günlük özet: bildirilecek bir şey yok, e-posta gönderilmedi")
            return {"ok": True, "sent": False, "message": "Bildirilecek kalem yok"}

        to = recipients(db)
        if not to:
            return {"ok": True, "sent": False, "message": "E-posta bildirimi açık kullanıcı yok"}

        subject, html, text = _render(digest)
        send_email(to, subject, html, text)
        return {"ok": True, "sent": True, "recipients": len(to), "items": total}
    except EmailNotConfigured as e:
        return {"ok": False, "message": str(e)}
    except Exception:
        logger.exception("Günlük özet e-postası gönderilemedi")
        return {"ok": False, "message": "Gönderim sırasında hata oluştu, sunucu loglarına bakın"}
    finally:
        db.close()

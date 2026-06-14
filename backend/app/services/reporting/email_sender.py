from __future__ import annotations

import json
import logging
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path

from app.core.config import settings
from app.services.evaluation.models import EvaluationReport
from app.services.reporting.pdf_renderer import render_report_pdf
from app.services.upload.service import (
    get_notification_email,
    is_notification_sent,
    mark_notification_sent,
    storage_dir,
    timestamp_now,
)

logger = logging.getLogger("app.reporting.email")

PDF_FILE_NAME = "degerlendirme-raporu.pdf"


def send_report_email(session_id: str, report: EvaluationReport) -> None:
    """Değerlendirme tamamlandığında rapor mailini gönderir (tab'dan bağımsız, sunucu tarafı).

    SMTP yapılandırılmamışsa gerçek gönderim yerine mail + PDF runtime/outbox altına yazılır
    (testable fallback). Hata değerlendirmeyi ETKİLEMEZ; yalnızca loglanır.
    """
    try:
        email = get_notification_email(session_id)
        if not email:
            logger.info("Session %s için bildirim e-postası yok; mail adımı atlandı.", session_id)
            return
        if is_notification_sent(session_id):
            logger.info("Session %s için rapor maili zaten gönderilmiş; tekrar gönderilmedi.", session_id)
            return

        pdf_bytes = render_report_pdf(report)
        subject = "TÜBİTAK Proje Öneri Değerlendirme Raporunuz Hazır"
        body = _compose_body(report)

        if settings.smtp_enabled and settings.smtp_host and settings.smtp_from_address:
            _send_via_smtp(recipient=email, subject=subject, body=body, pdf_bytes=pdf_bytes)
            logger.info("Rapor maili %s adresine gönderildi (session %s).", email, session_id)
        else:
            path = _write_to_outbox(
                session_id=session_id,
                recipient=email,
                subject=subject,
                body=body,
                pdf_bytes=pdf_bytes,
            )
            logger.warning(
                "SMTP devre dışı/eksik. Rapor maili gönderilmedi; payload + PDF outbox'a yazıldı: %s",
                path,
            )
        mark_notification_sent(session_id)
    except Exception as exc:  # noqa: BLE001 - mail hatası değerlendirmeyi çökertmemeli
        logger.exception("Rapor maili işlenemedi (session %s): %s", session_id, exc)


def _build_message(recipient: str, subject: str, body: str, pdf_bytes: bytes) -> EmailMessage:
    message = EmailMessage()
    from_address = settings.smtp_from_address or "no-reply@localhost"
    message["From"] = f"{settings.smtp_from_name} <{from_address}>"
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)
    message.add_attachment(
        pdf_bytes,
        maintype="application",
        subtype="pdf",
        filename=PDF_FILE_NAME,
    )
    return message


def _send_via_smtp(recipient: str, subject: str, body: str, pdf_bytes: bytes) -> None:
    message = _build_message(recipient, subject, body, pdf_bytes)
    if settings.smtp_use_tls:
        context = ssl.create_default_context()
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as server:
            server.starttls(context=context)
            if settings.smtp_username:
                server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(message)
    else:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as server:
            if settings.smtp_username:
                server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(message)


def _write_to_outbox(
    session_id: str,
    recipient: str,
    subject: str,
    body: str,
    pdf_bytes: bytes,
) -> Path:
    outbox_dir = storage_dir().parent / "outbox" / session_id
    outbox_dir.mkdir(parents=True, exist_ok=True)

    message = _build_message(recipient, subject, body, pdf_bytes)
    (outbox_dir / "message.eml").write_bytes(message.as_bytes())
    (outbox_dir / PDF_FILE_NAME).write_bytes(pdf_bytes)
    (outbox_dir / "payload.json").write_text(
        json.dumps(
            {
                "to": recipient,
                "from": settings.smtp_from_address or "(yapılandırılmadı)",
                "subject": subject,
                "body": body,
                "pdf_bytes": len(pdf_bytes),
                "written_at": timestamp_now(),
                "smtp_enabled": settings.smtp_enabled,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return outbox_dir


def _compose_body(report: EvaluationReport) -> str:
    lines = [
        "Merhaba,",
        "",
        "Yüklediğiniz proje önerisinin değerlendirmesi tamamlandı. Ayrıntılı rapor PDF olarak ektedir.",
        "",
        f"Genel Skor: {_fmt(report.overall_score)}/100",
        "",
        "Ana Boyut Skorları:",
    ]
    for dim in report.main_scores:
        lines.append(f"  - {dim.main_dimension_id} ({dim.title}): {_fmt(dim.score)}/100")
    if report.final_summary:
        lines.extend(["", report.final_summary])
    lines.extend(
        [
            "",
            "Tüm kriter bazlı bulgular, belge kanıtları ve eksik bilgiler ekteki PDF raporunda yer almaktadır.",
            "",
            "İyi çalışmalar,",
            settings.smtp_from_name,
        ]
    )
    return "\n".join(lines)


def _fmt(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.0f}" if float(value).is_integer() else f"{value:.1f}"

"""Email sender using SMTP."""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Optional

from app.config import settings

logger = logging.getLogger(__name__)


class EmailSender:
    """Send emails via SMTP."""

    def __init__(self):
        self.smtp_host = getattr(settings, 'smtp_host', 'smtp.gmail.com')
        self.smtp_port = getattr(settings, 'smtp_port', 587)
        self.smtp_user = getattr(settings, 'smtp_user', None)
        self.smtp_password = getattr(settings, 'smtp_password', None)
        self.from_email = getattr(settings, 'email_from', 'trademarks@example.com')
        self.from_name = getattr(settings, 'email_from_name', 'Trademark System')

    def send_email(
        self,
        to_emails: List[str],
        subject: str,
        html_body: str,
        text_body: Optional[str] = None,
    ) -> bool:
        """Send an email.

        Args:
            to_emails: List of recipient email addresses
            subject: Email subject
            html_body: HTML content of the email
            text_body: Plain text alternative (optional)

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.smtp_user or not self.smtp_password:
            logger.warning("SMTP credentials not configured, skipping email")
            return False

        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{self.from_name} <{self.from_email}>"
            msg['To'] = ', '.join(to_emails)

            # Add text part
            if text_body:
                part1 = MIMEText(text_body, 'plain', 'utf-8')
                msg.attach(part1)

            # Add HTML part
            part2 = MIMEText(html_body, 'html', 'utf-8')
            msg.attach(part2)

            # Send
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.sendmail(self.from_email, to_emails, msg.as_string())

            logger.info(f"Email sent to {to_emails}: {subject}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False

    def send_expiration_notification(
        self,
        to_emails: List[str],
        trademark_name: str,
        territory: str,
        registration_number: str,
        expiration_date: str,
        days_left: int,
    ) -> bool:
        """Send trademark expiration notification."""
        subject = f"[Важно] Истекает срок действия товарного знака: {trademark_name}"

        urgency_color = "#d32f2f" if days_left <= 30 else "#ef6c00" if days_left <= 90 else "#1976d2"

        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: {urgency_color};">Уведомление об истечении срока</h2>

        <p>Уважаемый пользователь,</p>

        <p>Срок действия товарного знака <strong>{trademark_name}</strong> истекает через
        <span style="color: {urgency_color}; font-weight: bold;">{days_left} дней</span>.</p>

        <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #eee; width: 40%;">
                    <strong>Товарный знак:</strong>
                </td>
                <td style="padding: 10px; border-bottom: 1px solid #eee;">{trademark_name}</td>
            </tr>
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #eee;">
                    <strong>Территория:</strong>
                </td>
                <td style="padding: 10px; border-bottom: 1px solid #eee;">{territory}</td>
            </tr>
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #eee;">
                    <strong>Номер регистрации:</strong>
                </td>
                <td style="padding: 10px; border-bottom: 1px solid #eee;">{registration_number}</td>
            </tr>
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #eee;">
                    <strong>Срок действия до:</strong>
                </td>
                <td style="padding: 10px; border-bottom: 1px solid #eee;">
                    <span style="color: {urgency_color}; font-weight: bold;">{expiration_date}</span>
                </td>
            </tr>
        </table>

        <div style="background: #f5f5f5; padding: 15px; border-radius: 5px; margin: 20px 0;">
            <p style="margin: 0;"><strong>Рекомендуемые действия:</strong></p>
            <ul style="margin: 10px 0; padding-left: 20px;">
                <li>Если планируется продление — подайте заявку на продление заблаговременно</li>
                <li>Если продление не планируется — отметьте это в системе для прекращения уведомлений</li>
            </ul>
        </div>

        <p style="color: #666; font-size: 12px; margin-top: 30px;">
            Это автоматическое уведомление от системы управления товарными знаками.
            <br>Чтобы отключить эти уведомления, отметьте "Продление подано" или
            "Решено не продлевать" в карточке регистрации.
        </p>
    </div>
</body>
</html>
"""

        text_body = f"""
Уведомление об истечении срока действия товарного знака

Товарный знак: {trademark_name}
Территория: {territory}
Номер регистрации: {registration_number}
Срок действия до: {expiration_date}
Осталось дней: {days_left}

Рекомендуемые действия:
- Если планируется продление — подайте заявку на продление заблаговременно
- Если продление не планируется — отметьте это в системе для прекращения уведомлений

---
Это автоматическое уведомление от системы управления товарными знаками.
"""

        return self.send_email(to_emails, subject, html_body, text_body)

    def send_status_change_notification(
        self,
        to_emails: List[str],
        trademark_name: str,
        territory: str,
        registration_number: str,
        old_status: str,
        new_status: str,
    ) -> bool:
        """Send notification about status change."""
        subject = f"Изменение статуса товарного знака: {trademark_name}"

        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #1976d2;">Изменение статуса регистрации</h2>

        <p>Статус товарного знака <strong>{trademark_name}</strong> был изменён.</p>

        <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #eee; width: 40%;">
                    <strong>Товарный знак:</strong>
                </td>
                <td style="padding: 10px; border-bottom: 1px solid #eee;">{trademark_name}</td>
            </tr>
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #eee;">
                    <strong>Территория:</strong>
                </td>
                <td style="padding: 10px; border-bottom: 1px solid #eee;">{territory}</td>
            </tr>
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #eee;">
                    <strong>Номер регистрации:</strong>
                </td>
                <td style="padding: 10px; border-bottom: 1px solid #eee;">{registration_number}</td>
            </tr>
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #eee;">
                    <strong>Предыдущий статус:</strong>
                </td>
                <td style="padding: 10px; border-bottom: 1px solid #eee;">{old_status}</td>
            </tr>
            <tr>
                <td style="padding: 10px; border-bottom: 1px solid #eee;">
                    <strong>Новый статус:</strong>
                </td>
                <td style="padding: 10px; border-bottom: 1px solid #eee;">
                    <span style="color: #1976d2; font-weight: bold;">{new_status}</span>
                </td>
            </tr>
        </table>

        <p style="color: #666; font-size: 12px; margin-top: 30px;">
            Это автоматическое уведомление от системы управления товарными знаками.
        </p>
    </div>
</body>
</html>
"""

        text_body = f"""
Изменение статуса товарного знака

Товарный знак: {trademark_name}
Территория: {territory}
Номер регистрации: {registration_number}
Предыдущий статус: {old_status}
Новый статус: {new_status}

---
Это автоматическое уведомление от системы управления товарными знаками.
"""

        return self.send_email(to_emails, subject, html_body, text_body)

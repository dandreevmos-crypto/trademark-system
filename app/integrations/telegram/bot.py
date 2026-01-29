"""Telegram bot for notifications."""

import logging
from typing import List, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Send notifications via Telegram bot."""

    def __init__(self):
        self.bot_token = getattr(settings, 'telegram_bot_token', None)
        self.default_chat_ids = getattr(settings, 'telegram_chat_ids', [])
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}"

    async def send_message(
        self,
        text: str,
        chat_ids: Optional[List[str]] = None,
        parse_mode: str = "HTML",
    ) -> dict:
        """Send message to Telegram chat(s).

        Args:
            text: Message text (supports HTML formatting)
            chat_ids: List of chat IDs to send to (uses default if not provided)
            parse_mode: Message parse mode (HTML or Markdown)

        Returns:
            Dict with results for each chat_id
        """
        if not self.bot_token:
            logger.warning("Telegram bot token not configured, skipping notification")
            return {"error": "Bot token not configured"}

        target_chats = chat_ids or self.default_chat_ids
        if not target_chats:
            logger.warning("No Telegram chat IDs configured")
            return {"error": "No chat IDs configured"}

        results = {}
        async with httpx.AsyncClient() as client:
            for chat_id in target_chats:
                try:
                    response = await client.post(
                        f"{self.api_url}/sendMessage",
                        json={
                            "chat_id": chat_id,
                            "text": text,
                            "parse_mode": parse_mode,
                            "disable_web_page_preview": True,
                        },
                        timeout=10.0,
                    )
                    response.raise_for_status()
                    results[chat_id] = {"success": True}
                    logger.info(f"Telegram message sent to {chat_id}")
                except Exception as e:
                    logger.error(f"Failed to send Telegram message to {chat_id}: {e}")
                    results[chat_id] = {"success": False, "error": str(e)}

        return results

    async def send_expiration_notification(
        self,
        trademark_name: str,
        territory: str,
        registration_number: str,
        expiration_date: str,
        days_left: int,
        chat_ids: Optional[List[str]] = None,
    ) -> dict:
        """Send trademark expiration notification."""
        urgency = ""
        if days_left <= 30:
            urgency = " (СРОЧНО)"
        elif days_left <= 90:
            urgency = " (Внимание)"

        text = f"""
<b>Истекает срок действия ТЗ{urgency}</b>

<b>Товарный знак:</b> {self._escape_html(trademark_name)}
<b>Территория:</b> {self._escape_html(territory)}
<b>Номер:</b> {registration_number}
<b>Срок до:</b> {expiration_date}
<b>Осталось:</b> {days_left} дней

<i>Отметьте "продление подано" или "не продлевать" для отключения уведомлений</i>
"""
        return await self.send_message(text.strip(), chat_ids)

    async def send_status_change_notification(
        self,
        trademark_name: str,
        territory: str,
        registration_number: str,
        old_status: str,
        new_status: str,
        chat_ids: Optional[List[str]] = None,
    ) -> dict:
        """Send status change notification."""
        text = f"""
<b>Изменён статус регистрации</b>

<b>Товарный знак:</b> {self._escape_html(trademark_name)}
<b>Территория:</b> {self._escape_html(territory)}
<b>Номер:</b> {registration_number}
<b>Было:</b> {old_status}
<b>Стало:</b> <b>{new_status}</b>
"""
        return await self.send_message(text.strip(), chat_ids)

    async def send_sync_error_notification(
        self,
        source: str,
        error_message: str,
        failed_count: int,
        chat_ids: Optional[List[str]] = None,
    ) -> dict:
        """Send sync error notification to admins."""
        text = f"""
<b>Ошибка синхронизации</b>

<b>Источник:</b> {source.upper()}
<b>Ошибка:</b> {self._escape_html(error_message[:200])}
<b>Неудачных попыток:</b> {failed_count}

<i>Требуется проверка настроек интеграции</i>
"""
        return await self.send_message(text.strip(), chat_ids)

    async def send_upcoming_summary(
        self,
        expiring_count: int,
        expiring_30_days: int,
        expiring_90_days: int,
        chat_ids: Optional[List[str]] = None,
    ) -> dict:
        """Send daily summary of upcoming expirations."""
        text = f"""
<b>Сводка по истекающим ТЗ</b>

Всего истекает в ближайшие 6 мес: <b>{expiring_count}</b>

В ближайшие 30 дней: <b>{expiring_30_days}</b>
В ближайшие 90 дней: <b>{expiring_90_days}</b>

<i>Проверьте статус продления в системе</i>
"""
        return await self.send_message(text.strip(), chat_ids)

    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters."""
        if not text:
            return ""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

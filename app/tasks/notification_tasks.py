"""Celery tasks for notification handling and sending."""

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone
from typing import List
from uuid import UUID

from celery import shared_task
from sqlalchemy import and_, select, func
from sqlalchemy.orm import selectinload

from app.database import async_session_maker
from app.models import TrademarkRegistration, Notification, User
from app.models.trademark import RenewalStatus, NotificationType
from app.config import settings
from app.integrations.email import EmailSender
from app.integrations.telegram import TelegramNotifier

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run async coroutine in sync context for Celery."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


async def _get_expiring_registrations(days: int) -> List[TrademarkRegistration]:
    """Get registrations expiring within specified days."""
    today = date.today()
    target_date = today + timedelta(days=days)

    async with async_session_maker() as session:
        query = (
            select(TrademarkRegistration)
            .where(
                and_(
                    TrademarkRegistration.expiration_date <= target_date,
                    TrademarkRegistration.expiration_date >= today,
                    TrademarkRegistration.renewal_status == RenewalStatus.ACTIVE.value,
                )
            )
            .options(
                selectinload(TrademarkRegistration.trademark),
                selectinload(TrademarkRegistration.territory),
            )
            .order_by(TrademarkRegistration.expiration_date.asc())
        )

        result = await session.execute(query)
        return result.scalars().all()


async def _check_notification_exists(
    registration_id: UUID,
    notification_type: str,
    within_days: int = 7,
) -> bool:
    """Check if notification was already sent recently."""
    async with async_session_maker() as session:
        cutoff = datetime.now(timezone.utc) - timedelta(days=within_days)

        query = select(func.count(Notification.id)).where(
            and_(
                Notification.registration_id == registration_id,
                Notification.notification_type == notification_type,
                Notification.created_at >= cutoff,
            )
        )
        result = await session.execute(query)
        count = result.scalar()
        return count > 0


async def _create_notification(
    registration_id: UUID,
    notification_type: str,
    trigger_date: date,
    email_sent: bool = False,
    telegram_sent: bool = False,
) -> Notification:
    """Create a new notification record."""
    async with async_session_maker() as session:
        notification = Notification(
            registration_id=registration_id,
            notification_type=notification_type,
            trigger_date=trigger_date,
            scheduled_send_date=date.today(),
            email_sent_at=datetime.now(timezone.utc) if email_sent else None,
            email_status="sent" if email_sent else None,
            telegram_sent_at=datetime.now(timezone.utc) if telegram_sent else None,
            telegram_status="sent" if telegram_sent else None,
        )
        session.add(notification)
        await session.commit()
        return notification


async def _get_admin_emails() -> List[str]:
    """Get email addresses of admin users."""
    async with async_session_maker() as session:
        query = select(User.email).where(
            and_(User.role == "admin", User.is_active == True)
        )
        result = await session.execute(query)
        return [row[0] for row in result.all()]


async def _send_email_notification(
    admin_emails: List[str],
    registration: TrademarkRegistration,
    days_remaining: int,
) -> bool:
    """Send email notification."""
    if not admin_emails:
        return False

    email_sender = EmailSender()

    trademark_name = registration.trademark.name if registration.trademark else "Unknown"
    territory = registration.territory.name_ru if registration.territory else "Unknown"
    reg_number = registration.registration_number or registration.application_number or "-"
    exp_date = registration.expiration_date.strftime("%d.%m.%Y")

    return email_sender.send_expiration_notification(
        to_emails=admin_emails,
        trademark_name=trademark_name,
        territory=territory,
        registration_number=reg_number,
        expiration_date=exp_date,
        days_left=days_remaining,
    )


async def _send_telegram_notification(
    registration: TrademarkRegistration,
    days_remaining: int,
) -> bool:
    """Send Telegram notification."""
    telegram = TelegramNotifier()

    trademark_name = registration.trademark.name if registration.trademark else "Unknown"
    territory = registration.territory.name_ru if registration.territory else "Unknown"
    reg_number = registration.registration_number or registration.application_number or "-"
    exp_date = registration.expiration_date.strftime("%d.%m.%Y")

    try:
        result = await telegram.send_expiration_notification(
            trademark_name=trademark_name,
            territory=territory,
            registration_number=reg_number,
            expiration_date=exp_date,
            days_left=days_remaining,
        )
        # Check if any message was sent successfully
        if isinstance(result, dict):
            return any(r.get("success") for r in result.values() if isinstance(r, dict))
        return False
    except Exception as e:
        logger.error(f"Telegram notification failed: {e}")
        return False


async def _process_notifications_for_interval(days: int) -> dict:
    """Process notifications for a specific interval (180, 90, or 30 days)."""
    # Determine notification type
    if days >= 180:
        notification_type = NotificationType.EXPIRATION_180.value
    elif days >= 90:
        notification_type = NotificationType.EXPIRATION_90.value
    else:
        notification_type = NotificationType.EXPIRATION_30.value

    registrations = await _get_expiring_registrations(days)
    admin_emails = await _get_admin_emails()

    stats = {
        "registrations_found": len(registrations),
        "notifications_created": 0,
        "emails_sent": 0,
        "telegrams_sent": 0,
        "skipped": 0,
    }

    for registration in registrations:
        # Skip if renewal filed or not renewing
        if registration.renewal_status in [
            RenewalStatus.RENEWAL_FILED.value,
            RenewalStatus.NOT_RENEWING.value,
            RenewalStatus.EXPIRED.value,
        ]:
            stats["skipped"] += 1
            continue

        # Calculate actual days remaining
        days_remaining = (registration.expiration_date - date.today()).days

        # Determine which notification window applies
        if days_remaining > 90:
            current_type = NotificationType.EXPIRATION_180.value
        elif days_remaining > 30:
            current_type = NotificationType.EXPIRATION_90.value
        else:
            current_type = NotificationType.EXPIRATION_30.value

        # Skip if not in current check window
        if current_type != notification_type:
            continue

        # Check if notification already exists
        if await _check_notification_exists(registration.id, notification_type):
            stats["skipped"] += 1
            continue

        # Send notifications
        email_sent = await _send_email_notification(
            admin_emails, registration, days_remaining
        )
        telegram_sent = await _send_telegram_notification(
            registration, days_remaining
        )

        # Create notification record
        await _create_notification(
            registration.id,
            notification_type,
            registration.expiration_date,
            email_sent=email_sent,
            telegram_sent=telegram_sent,
        )

        stats["notifications_created"] += 1
        if email_sent:
            stats["emails_sent"] += 1
        if telegram_sent:
            stats["telegrams_sent"] += 1

        logger.info(
            f"Notification sent for {registration.trademark.name if registration.trademark else 'Unknown'}: "
            f"email={email_sent}, telegram={telegram_sent}"
        )

    return stats


async def _send_daily_summary():
    """Send daily summary of expiring trademarks via Telegram."""
    telegram = TelegramNotifier()

    # Get all expiring registrations
    all_expiring = await _get_expiring_registrations(180)
    expiring_30 = [r for r in all_expiring if (r.expiration_date - date.today()).days <= 30]
    expiring_90 = [r for r in all_expiring if (r.expiration_date - date.today()).days <= 90]

    await telegram.send_upcoming_summary(
        expiring_count=len(all_expiring),
        expiring_30_days=len(expiring_30),
        expiring_90_days=len(expiring_90),
    )


@shared_task(name="check_expiring_trademarks")
def check_expiring_trademarks() -> dict:
    """
    Check for trademarks expiring at configured intervals and send notifications.

    This task runs daily (typically at 9:00 AM Moscow time) and checks for
    trademarks expiring at:
    - 180 days (6 months)
    - 90 days (3 months)
    - 30 days (1 month)

    Notifications are suppressed if:
    - renewal_status = 'renewal_filed'
    - renewal_status = 'not_renewing'
    - Already notified within 7 days for this interval
    """
    intervals = getattr(settings, 'notification_intervals_days', [180, 90, 30])

    async def process_all():
        results = {}
        for days in intervals:
            results[f"{days}_days"] = await _process_notifications_for_interval(days)
        return results

    return _run_async(process_all())


@shared_task(name="send_daily_summary")
def send_daily_summary() -> dict:
    """
    Send daily summary of upcoming expirations to Telegram.

    Runs daily at 10:00 AM Moscow time.
    """
    _run_async(_send_daily_summary())
    return {"status": "sent"}


@shared_task(name="send_status_change_notification")
def send_status_change_notification(
    registration_id: str,
    trademark_name: str,
    territory: str,
    registration_number: str,
    old_status: str,
    new_status: str,
) -> dict:
    """
    Send notification about status change.

    Called when sync detects a status change.
    """
    async def _send():
        email_sender = EmailSender()
        telegram = TelegramNotifier()

        admin_emails = await _get_admin_emails()

        email_sent = False
        telegram_sent = False

        # Send email
        if admin_emails:
            email_sent = email_sender.send_status_change_notification(
                to_emails=admin_emails,
                trademark_name=trademark_name,
                territory=territory,
                registration_number=registration_number,
                old_status=old_status,
                new_status=new_status,
            )

        # Send Telegram
        try:
            result = await telegram.send_status_change_notification(
                trademark_name=trademark_name,
                territory=territory,
                registration_number=registration_number,
                old_status=old_status,
                new_status=new_status,
            )
            if isinstance(result, dict):
                telegram_sent = any(r.get("success") for r in result.values() if isinstance(r, dict))
        except Exception as e:
            logger.error(f"Telegram notification failed: {e}")

        return {
            "registration_id": registration_id,
            "email_sent": email_sent,
            "telegram_sent": telegram_sent,
        }

    return _run_async(_send())


@shared_task(name="send_notification")
def send_notification(registration_id: str, notification_type: str) -> dict:
    """Send a specific notification for a registration."""

    async def process():
        async with async_session_maker() as session:
            query = (
                select(TrademarkRegistration)
                .where(TrademarkRegistration.id == UUID(registration_id))
                .options(
                    selectinload(TrademarkRegistration.trademark),
                    selectinload(TrademarkRegistration.territory),
                )
            )
            result = await session.execute(query)
            registration = result.scalar_one_or_none()

            if not registration:
                return {"error": "Registration not found"}

            admin_emails = await _get_admin_emails()

            # Calculate days remaining
            days_remaining = (registration.expiration_date - date.today()).days

            email_sent = await _send_email_notification(
                admin_emails, registration, days_remaining
            )
            telegram_sent = await _send_telegram_notification(
                registration, days_remaining
            )

            return {
                "registration_id": registration_id,
                "email_sent": email_sent,
                "telegram_sent": telegram_sent,
            }

    return _run_async(process())

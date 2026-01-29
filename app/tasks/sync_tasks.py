"""Celery tasks for synchronization with FIPS and WIPO."""

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from celery import shared_task
from sqlalchemy import and_, select, update
from sqlalchemy.orm import selectinload

from app.database import async_session_maker
from app.models import TrademarkRegistration, SyncLog, Trademark, TrademarkClass
from app.models.trademark import RenewalStatus, RegistrationStatus

logger = logging.getLogger(__name__)


async def _get_registrations_for_sync(
    source: str,
    limit: int = 100,
    priority_first: bool = True,
) -> list:
    """Get registrations that need syncing."""
    async with async_session_maker() as session:
        # Base query
        query = select(TrademarkRegistration).options(
            selectinload(TrademarkRegistration.trademark),
            selectinload(TrademarkRegistration.territory),
        )

        # Filter by source
        if source == "fips":
            query = query.where(
                and_(
                    TrademarkRegistration.is_national == True,
                    TrademarkRegistration.renewal_status == RenewalStatus.ACTIVE.value,
                )
            )
        elif source == "wipo":
            query = query.where(
                and_(
                    TrademarkRegistration.is_international == True,
                    TrademarkRegistration.renewal_status == RenewalStatus.ACTIVE.value,
                )
            )

        # Priority: registrations expiring soon
        if priority_first:
            query = query.order_by(
                # Expiring soon first
                TrademarkRegistration.expiration_date.asc().nulls_last(),
                # Then by last sync (oldest first)
                TrademarkRegistration.last_sync_at.asc().nulls_first(),
            )
        else:
            query = query.order_by(
                TrademarkRegistration.last_sync_at.asc().nulls_first()
            )

        query = query.limit(limit)
        result = await session.execute(query)
        return result.scalars().all()


async def _log_sync_result(
    registration_id: Optional[UUID],
    source: str,
    operation: str,
    status: str,
    changes_detected: Optional[dict] = None,
    error_message: Optional[str] = None,
    duration_ms: Optional[int] = None,
) -> None:
    """Log sync operation result."""
    async with async_session_maker() as session:
        log = SyncLog(
            registration_id=registration_id,
            source=source,
            operation=operation,
            status=status,
            changes_detected=changes_detected,
            error_message=error_message,
            duration_ms=duration_ms,
        )
        session.add(log)
        await session.commit()


async def _update_registration_from_fips(
    registration_id: UUID,
    fips_data: 'FIPSTrademarkData',
) -> dict:
    """Update registration with data from FIPS."""
    from app.integrations.fips import FIPSScraper

    changes = {}

    async with async_session_maker() as session:
        query = select(TrademarkRegistration).where(
            TrademarkRegistration.id == registration_id
        )
        result = await session.execute(query)
        registration = result.scalar_one_or_none()

        if not registration:
            return {"error": "Registration not found"}

        # Compare and update fields
        if fips_data.expiration_date and fips_data.expiration_date != registration.expiration_date:
            changes["expiration_date"] = {
                "old": str(registration.expiration_date),
                "new": str(fips_data.expiration_date)
            }
            registration.expiration_date = fips_data.expiration_date

        if fips_data.status:
            new_status = _map_fips_status(fips_data.status)
            if new_status and new_status != registration.status:
                changes["status"] = {
                    "old": registration.status,
                    "new": new_status
                }
                registration.status = new_status

        if fips_data.registration_date and fips_data.registration_date != registration.registration_date:
            changes["registration_date"] = {
                "old": str(registration.registration_date),
                "new": str(fips_data.registration_date)
            }
            registration.registration_date = fips_data.registration_date

        # Update last sync time
        registration.last_sync_at = datetime.now(timezone.utc)
        registration.last_sync_source = "fips"

        await session.commit()

        # Update goods/services descriptions if available
        if fips_data.goods_services:
            await _update_goods_services(registration.trademark_id, fips_data.goods_services)
            changes["goods_services_updated"] = list(fips_data.goods_services.keys())

    return changes


async def _update_goods_services(trademark_id: UUID, goods_services: dict[int, str]) -> None:
    """Update goods/services descriptions for trademark classes."""
    async with async_session_maker() as session:
        for class_num, description in goods_services.items():
            # Find the class record
            query = select(TrademarkClass).where(
                and_(
                    TrademarkClass.trademark_id == trademark_id,
                    TrademarkClass.icgs_class == class_num,
                )
            )
            result = await session.execute(query)
            tm_class = result.scalar_one_or_none()

            if tm_class:
                # Update existing
                if tm_class.goods_services_description != description:
                    tm_class.goods_services_description = description
            else:
                # Create new class record
                new_class = TrademarkClass(
                    trademark_id=trademark_id,
                    icgs_class=class_num,
                    goods_services_description=description,
                )
                session.add(new_class)

        await session.commit()


async def _update_registration_from_wipo(
    registration_id: UUID,
    wipo_data: 'WIPOTrademarkData',
) -> dict:
    """Update registration with data from WIPO."""
    changes = {}

    async with async_session_maker() as session:
        query = select(TrademarkRegistration).where(
            TrademarkRegistration.id == registration_id
        )
        result = await session.execute(query)
        registration = result.scalar_one_or_none()

        if not registration:
            return {"error": "Registration not found"}

        # Compare and update fields
        if wipo_data.expiration_date and wipo_data.expiration_date != registration.expiration_date:
            changes["expiration_date"] = {
                "old": str(registration.expiration_date),
                "new": str(wipo_data.expiration_date)
            }
            registration.expiration_date = wipo_data.expiration_date

        if wipo_data.status:
            new_status = _map_wipo_status(wipo_data.status)
            if new_status and new_status != registration.status:
                changes["status"] = {
                    "old": registration.status,
                    "new": new_status
                }
                registration.status = new_status

        # Update last sync time
        registration.last_sync_at = datetime.now(timezone.utc)
        registration.last_sync_source = "wipo"

        await session.commit()

    return changes


def _map_fips_status(fips_status: str) -> Optional[str]:
    """Map FIPS status to our status enum."""
    status_map = {
        "registered": RegistrationStatus.REGISTERED.value,
        "pending": RegistrationStatus.PENDING.value,
        "rejected": RegistrationStatus.REJECTED.value,
        "terminated": RegistrationStatus.TERMINATED.value,
        "expired": RegistrationStatus.TERMINATED.value,
    }
    return status_map.get(fips_status.lower())


def _map_wipo_status(wipo_status: str) -> Optional[str]:
    """Map WIPO status to our status enum."""
    status_map = {
        "registered": RegistrationStatus.REGISTERED.value,
        "pending": RegistrationStatus.PENDING.value,
        "rejected": RegistrationStatus.REJECTED.value,
        "terminated": RegistrationStatus.TERMINATED.value,
        "expired": RegistrationStatus.TERMINATED.value,
    }
    return status_map.get(wipo_status.lower())


async def _sync_fips_registration(registration: TrademarkRegistration) -> dict:
    """
    Sync a single registration with FIPS.
    """
    from app.integrations.fips import FIPSScraper
    from app.integrations.storage import MinIOStorage

    start_time = datetime.now(timezone.utc)
    result = {
        "registration_id": str(registration.id),
        "status": "error",
        "changes": {},
        "message": "",
    }

    # Get registration number to look up
    reg_number = registration.registration_number
    if not reg_number:
        result["message"] = "No registration number"
        result["status"] = "skipped"
        return result

    try:
        async with FIPSScraper() as scraper:
            # Fetch data from FIPS
            fips_data = await scraper.get_trademark_by_number(reg_number)

            if fips_data.error:
                result["message"] = fips_data.error
                result["status"] = "error"

                await _log_sync_result(
                    registration.id,
                    "fips",
                    "status_check",
                    "failed",
                    error_message=fips_data.error,
                    duration_ms=int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000),
                )
                return result

            # Update registration with FIPS data
            changes = await _update_registration_from_fips(registration.id, fips_data)

            # Download and store image if available
            if fips_data.image_url:
                async with MinIOStorage() as storage:
                    stored_path = await storage.download_and_upload_image(
                        fips_data.image_url,
                        str(registration.trademark_id),
                        source="fips"
                    )
                    if stored_path:
                        # Update trademark image path
                        async with async_session_maker() as session:
                            stmt = update(Trademark).where(
                                Trademark.id == registration.trademark_id
                            ).values(image_path=stored_path, image_source="fips")
                            await session.execute(stmt)
                            await session.commit()
                        changes["image"] = {"new": stored_path}

            result["changes"] = changes
            result["status"] = "updated" if changes else "unchanged"
            result["message"] = f"Found {len(changes)} changes" if changes else "No changes"

            # Log success
            await _log_sync_result(
                registration.id,
                "fips",
                "status_check",
                "success",
                changes_detected=changes if changes else None,
                duration_ms=int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000),
            )

    except Exception as e:
        logger.exception(f"Error syncing FIPS registration {registration.id}: {e}")
        result["message"] = str(e)
        result["status"] = "error"

        await _log_sync_result(
            registration.id,
            "fips",
            "status_check",
            "failed",
            error_message=str(e),
            duration_ms=int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000),
        )

    return result


async def _sync_wipo_registration(registration: TrademarkRegistration) -> dict:
    """
    Sync a single registration with WIPO Madrid Monitor.
    """
    from app.integrations.wipo import WIPOClient
    from app.integrations.storage import MinIOStorage

    start_time = datetime.now(timezone.utc)
    result = {
        "registration_id": str(registration.id),
        "status": "error",
        "changes": {},
        "message": "",
    }

    # Get international number to look up
    int_number = registration.madrid_registration_number or registration.registration_number
    if not int_number:
        result["message"] = "No international registration number"
        result["status"] = "skipped"
        return result

    try:
        async with WIPOClient() as client:
            # Fetch data from WIPO
            wipo_data = await client.get_trademark_by_number(int_number)

            if wipo_data.error:
                result["message"] = wipo_data.error
                result["status"] = "error"

                await _log_sync_result(
                    registration.id,
                    "wipo",
                    "status_check",
                    "failed",
                    error_message=wipo_data.error,
                    duration_ms=int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000),
                )
                return result

            # Update registration with WIPO data
            changes = await _update_registration_from_wipo(registration.id, wipo_data)

            # Download and store image if available
            if wipo_data.image_url:
                async with MinIOStorage() as storage:
                    stored_path = await storage.download_and_upload_image(
                        wipo_data.image_url,
                        str(registration.trademark_id),
                        source="wipo"
                    )
                    if stored_path:
                        # Update trademark image path
                        async with async_session_maker() as session:
                            stmt = update(Trademark).where(
                                Trademark.id == registration.trademark_id
                            ).values(image_path=stored_path, image_source="wipo")
                            await session.execute(stmt)
                            await session.commit()
                        changes["image"] = {"new": stored_path}

            result["changes"] = changes
            result["status"] = "updated" if changes else "unchanged"
            result["message"] = f"Found {len(changes)} changes" if changes else "No changes"

            # Log success
            await _log_sync_result(
                registration.id,
                "wipo",
                "status_check",
                "success",
                changes_detected=changes if changes else None,
                duration_ms=int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000),
            )

    except Exception as e:
        logger.exception(f"Error syncing WIPO registration {registration.id}: {e}")
        result["message"] = str(e)
        result["status"] = "error"

        await _log_sync_result(
            registration.id,
            "wipo",
            "status_check",
            "failed",
            error_message=str(e),
            duration_ms=int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000),
        )

    return result


def _run_async(coro):
    """Run async coroutine in sync context."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(coro)


@shared_task(name="app.tasks.sync_tasks.sync_fips_trademarks")
def sync_fips_trademarks(limit: int = 50) -> dict:
    """
    Sync Russian trademarks with FIPS registry.

    This task:
    1. Gets registrations marked as national (Russian)
    2. Prioritizes those expiring within 6 months
    3. Checks FIPS for current status
    4. Updates local database if changes detected
    5. Downloads trademark images if missing

    Rate limit: 12 requests per minute (1 every 5 seconds)
    """

    async def process():
        registrations = await _get_registrations_for_sync("fips", limit=limit)

        logger.info(f"Starting FIPS sync for {len(registrations)} registrations")

        results = {
            "total": len(registrations),
            "synced": 0,
            "updated": 0,
            "unchanged": 0,
            "errors": 0,
            "skipped": 0,
        }

        for registration in registrations:
            try:
                result = await _sync_fips_registration(registration)

                if result["status"] == "updated":
                    results["updated"] += 1
                elif result["status"] == "unchanged":
                    results["unchanged"] += 1
                elif result["status"] == "error":
                    results["errors"] += 1
                else:
                    results["skipped"] += 1

                results["synced"] += 1

            except Exception as e:
                logger.exception(f"Error syncing registration {registration.id}: {e}")
                results["errors"] += 1

        logger.info(f"FIPS sync completed: {results}")
        return results

    return _run_async(process())


@shared_task(name="app.tasks.sync_tasks.sync_wipo_trademarks")
def sync_wipo_trademarks(limit: int = 50) -> dict:
    """
    Sync international trademarks with WIPO Madrid Monitor.

    This task:
    1. Gets registrations marked as international
    2. Prioritizes those expiring within 6 months
    3. Checks WIPO for current status
    4. Updates local database if changes detected

    Rate limit: 10 requests per minute
    """

    async def process():
        registrations = await _get_registrations_for_sync("wipo", limit=limit)

        logger.info(f"Starting WIPO sync for {len(registrations)} registrations")

        results = {
            "total": len(registrations),
            "synced": 0,
            "updated": 0,
            "unchanged": 0,
            "errors": 0,
            "skipped": 0,
        }

        for registration in registrations:
            try:
                result = await _sync_wipo_registration(registration)

                if result["status"] == "updated":
                    results["updated"] += 1
                elif result["status"] == "unchanged":
                    results["unchanged"] += 1
                elif result["status"] == "error":
                    results["errors"] += 1
                else:
                    results["skipped"] += 1

                results["synced"] += 1

            except Exception as e:
                logger.exception(f"Error syncing registration {registration.id}: {e}")
                results["errors"] += 1

        logger.info(f"WIPO sync completed: {results}")
        return results

    return _run_async(process())


@shared_task(name="app.tasks.sync_tasks.full_reconciliation")
def full_reconciliation() -> dict:
    """
    Perform full database reconciliation.

    This weekly task:
    1. Checks all active registrations
    2. Identifies discrepancies with external sources
    3. Generates reconciliation report
    """

    async def process():
        results = {
            "fips_checked": 0,
            "wipo_checked": 0,
            "discrepancies_found": 0,
            "errors": 0,
        }

        # Get all active registrations
        async with async_session_maker() as session:
            query = select(TrademarkRegistration).where(
                TrademarkRegistration.renewal_status == RenewalStatus.ACTIVE.value
            )
            result = await session.execute(query)
            registrations = result.scalars().all()

            for reg in registrations:
                if reg.is_national:
                    results["fips_checked"] += 1
                if reg.is_international:
                    results["wipo_checked"] += 1

        # Log reconciliation
        await _log_sync_result(
            None,
            "system",
            "reconciliation",
            "completed",
            changes_detected=results,
        )

        logger.info(f"Reconciliation completed: {results}")
        return results

    return _run_async(process())


@shared_task(name="app.tasks.sync_tasks.sync_single_registration")
def sync_single_registration(registration_id: str, source: str) -> dict:
    """Sync a single registration on demand."""

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

            if source == "fips":
                return await _sync_fips_registration(registration)
            elif source == "wipo":
                return await _sync_wipo_registration(registration)
            else:
                return {"error": f"Unknown source: {source}"}

    return _run_async(process())


@shared_task(name="app.tasks.sync_tasks.sync_priority_registrations")
def sync_priority_registrations() -> dict:
    """
    Sync registrations expiring within 6 months.

    Run daily to ensure expiring trademarks are up-to-date.
    """

    async def process():
        results = {
            "fips": {"total": 0, "updated": 0, "errors": 0},
            "wipo": {"total": 0, "updated": 0, "errors": 0},
        }

        priority_date = date.today() + timedelta(days=180)

        async with async_session_maker() as session:
            # Get FIPS registrations expiring soon
            fips_query = select(TrademarkRegistration).options(
                selectinload(TrademarkRegistration.trademark),
            ).where(
                and_(
                    TrademarkRegistration.is_national == True,
                    TrademarkRegistration.renewal_status == RenewalStatus.ACTIVE.value,
                    TrademarkRegistration.expiration_date <= priority_date,
                    TrademarkRegistration.expiration_date >= date.today(),
                )
            ).order_by(TrademarkRegistration.expiration_date.asc())

            result = await session.execute(fips_query)
            fips_regs = result.scalars().all()
            results["fips"]["total"] = len(fips_regs)

            # Get WIPO registrations expiring soon
            wipo_query = select(TrademarkRegistration).options(
                selectinload(TrademarkRegistration.trademark),
            ).where(
                and_(
                    TrademarkRegistration.is_international == True,
                    TrademarkRegistration.renewal_status == RenewalStatus.ACTIVE.value,
                    TrademarkRegistration.expiration_date <= priority_date,
                    TrademarkRegistration.expiration_date >= date.today(),
                )
            ).order_by(TrademarkRegistration.expiration_date.asc())

            result = await session.execute(wipo_query)
            wipo_regs = result.scalars().all()
            results["wipo"]["total"] = len(wipo_regs)

        # Sync FIPS registrations
        for reg in fips_regs:
            try:
                sync_result = await _sync_fips_registration(reg)
                if sync_result["status"] == "updated":
                    results["fips"]["updated"] += 1
            except Exception as e:
                logger.error(f"Priority FIPS sync error for {reg.id}: {e}")
                results["fips"]["errors"] += 1

        # Sync WIPO registrations
        for reg in wipo_regs:
            try:
                sync_result = await _sync_wipo_registration(reg)
                if sync_result["status"] == "updated":
                    results["wipo"]["updated"] += 1
            except Exception as e:
                logger.error(f"Priority WIPO sync error for {reg.id}: {e}")
                results["wipo"]["errors"] += 1

        logger.info(f"Priority sync completed: {results}")
        return results

    return _run_async(process())

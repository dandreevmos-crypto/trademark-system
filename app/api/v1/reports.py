"""Reports and export API endpoints."""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models import User
from app.schemas.trademark import TrademarkExportFilters
from app.services.export_service import ExportService

router = APIRouter()


@router.post("/export/excel")
async def export_trademarks_excel(
    filters: TrademarkExportFilters,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """
    Export trademarks to Excel with filters.

    Filters:
    - rights_holder_ids: Filter by specific rights holders
    - territory_ids: Filter by territories
    - icgs_classes: Filter by ICGS classes (1-45)
    - product_groups: Filter by product groups
    - statuses: Filter by registration status
    - renewal_statuses: Filter by renewal status
    - expiration_from/to: Filter by expiration date range
    - include_expired: Include expired registrations
    - include_rejected: Include rejected registrations
    """
    export_service = ExportService(db)
    excel_bytes = await export_service.export_to_excel(filters)

    filename = f"trademarks_export_{date.today().isoformat()}.xlsx"

    return StreamingResponse(
        iter([excel_bytes]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(excel_bytes)),
        },
    )


@router.get("/export/excel")
async def export_all_trademarks_excel(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    include_expired: bool = Query(False),
    include_rejected: bool = Query(False),
) -> StreamingResponse:
    """Export all trademarks to Excel (with optional expired/rejected)."""
    filters = TrademarkExportFilters(
        include_expired=include_expired,
        include_rejected=include_rejected,
    )

    export_service = ExportService(db)
    excel_bytes = await export_service.export_to_excel(filters)

    filename = f"trademarks_export_{date.today().isoformat()}.xlsx"

    return StreamingResponse(
        iter([excel_bytes]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(excel_bytes)),
        },
    )

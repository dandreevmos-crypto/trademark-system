"""Trademark API endpoints."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, get_current_admin_user
from app.database import get_db
from app.models import User, Trademark, TrademarkClass, TrademarkRegistration, RightsHolder, Territory
from app.schemas.trademark import (
    TrademarkCreate,
    TrademarkUpdate,
    TrademarkResponse,
    TrademarkListResponse,
    RightsHolderResponse,
    TerritoryResponse,
)

router = APIRouter()

# ICGS (Nice Classification) directory with keywords for search
ICGS_DIRECTORY = {
    1: "химические продукты, удобрения, клеи, chemical",
    2: "краски, лаки, покрытия, paints",
    3: "косметика, парфюмерия, мыло, шампунь, зубная паста, cosmetics, perfume, soap",
    4: "масла, смазки, топливо, свечи, oils, fuels",
    5: "фармацевтика, лекарства, медицинские препараты, витамины, pharmaceutical, medicines",
    6: "металлы, металлоизделия, скобяные изделия, metals",
    7: "машины, станки, двигатели, machines, motors",
    8: "ручные инструменты, ножи, бритвы, tools, knives",
    9: "электроника, компьютеры, телефоны, программы, приложения, electronics, computers, software, apps",
    10: "медицинское оборудование, протезы, medical equipment",
    11: "освещение, отопление, кондиционеры, сантехника, lighting, heating",
    12: "транспорт, автомобили, велосипеды, vehicles, cars, bicycles",
    13: "оружие, боеприпасы, фейерверки, weapons, fireworks",
    14: "ювелирные изделия, часы, драгоценности, jewelry, watches",
    15: "музыкальные инструменты, musical instruments",
    16: "бумага, канцтовары, типография, paper, stationery, printing",
    17: "резина, пластик, изоляционные материалы, rubber, plastic",
    18: "кожа, сумки, чемоданы, зонты, leather, bags, luggage, umbrellas",
    19: "строительные материалы, стекло, бетон, building materials",
    20: "мебель, зеркала, рамки, furniture, mirrors",
    21: "посуда, кухонная утварь, щетки, kitchenware, brushes",
    22: "веревки, канаты, палатки, мешки, ropes, tents, bags",
    23: "пряжа, нити, yarns, threads",
    24: "ткани, текстиль, постельное белье, textiles, fabrics, bed linen",
    25: "одежда, обувь, головные уборы, clothing, footwear, shoes, headwear, fashion",
    26: "кружева, ленты, пуговицы, молнии, lace, ribbons, buttons, zippers",
    27: "ковры, коврики, обои, carpets, rugs, wallpaper",
    28: "игры, игрушки, спортивные товары, games, toys, sports",
    29: "мясо, рыба, молочные продукты, консервы, meat, fish, dairy, canned food",
    30: "кофе, чай, какао, хлеб, кондитерские изделия, шоколад, coffee, tea, bread, confectionery, chocolate",
    31: "сельхозпродукция, фрукты, овощи, семена, корма, agricultural, fruits, vegetables, seeds",
    32: "пиво, напитки безалкогольные, вода, соки, beer, soft drinks, water, juices",
    33: "алкогольные напитки, вино, водка, коньяк, alcoholic beverages, wine, vodka",
    34: "табак, сигареты, спички, tobacco, cigarettes",
    35: "реклама, маркетинг, бизнес, торговля, advertising, marketing, business, retail",
    36: "страхование, финансы, банковское дело, недвижимость, insurance, finance, banking, real estate",
    37: "строительство, ремонт, установка, construction, repair, installation",
    38: "телекоммуникации, связь, интернет, telecommunications, internet",
    39: "транспортировка, логистика, доставка, путешествия, transportation, logistics, delivery, travel",
    40: "обработка материалов, printing, processing",
    41: "образование, развлечения, спорт, культура, education, entertainment, sports, culture",
    42: "научные исследования, IT услуги, разработка ПО, дизайн, research, IT services, software development, design",
    43: "рестораны, отели, кафе, общепит, restaurants, hotels, catering",
    44: "медицинские услуги, салоны красоты, ветеринария, medical services, beauty salons, veterinary",
    45: "юридические услуги, охрана, legal services, security",
}


def get_icgs_classes_by_keyword(keyword: str) -> List[int]:
    """Find ICGS classes matching a keyword."""
    keyword_lower = keyword.lower()
    matching = []
    for class_num, description in ICGS_DIRECTORY.items():
        if keyword_lower in description.lower():
            matching.append(class_num)
    return matching


@router.get("", response_model=TrademarkListResponse)
async def list_trademarks(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    goods_search: Optional[str] = Query(None, description="Поиск по товарам/услугам (например: обувь, косметика)"),
    rights_holder_id: Optional[UUID] = None,
    territory_id: Optional[int] = None,
    icgs_class: Optional[int] = None,
    status: Optional[str] = None,
    renewal_status: Optional[str] = None,
) -> TrademarkListResponse:
    """List trademarks with filtering and pagination."""
    # Base query
    query = select(Trademark).options(
        selectinload(Trademark.rights_holder),
        selectinload(Trademark.classes),
        selectinload(Trademark.registrations).selectinload(TrademarkRegistration.territory),
    )

    # Track if we already joined TrademarkClass
    joined_class = False

    # Apply filters
    if search:
        query = query.where(Trademark.name.ilike(f"%{search}%"))

    # Search by goods/services description or by ICGS class names
    if goods_search:
        # Get classes matching the search term from ICGS directory
        matching_classes = get_icgs_classes_by_keyword(goods_search)
        if matching_classes:
            query = query.join(TrademarkClass).where(
                TrademarkClass.icgs_class.in_(matching_classes)
            )
            joined_class = True
        else:
            # Fallback to description search if exists
            query = query.join(TrademarkClass).where(
                TrademarkClass.goods_services_description.ilike(f"%{goods_search}%")
            )
            joined_class = True

    if rights_holder_id:
        query = query.where(Trademark.rights_holder_id == rights_holder_id)

    if territory_id:
        query = query.join(TrademarkRegistration).where(
            TrademarkRegistration.territory_id == territory_id
        )

    if icgs_class:
        if not joined_class:
            query = query.join(TrademarkClass)
            joined_class = True
        query = query.where(TrademarkClass.icgs_class == icgs_class)

    if status:
        if not territory_id:
            query = query.join(TrademarkRegistration)
        query = query.where(TrademarkRegistration.status == status)

    if renewal_status:
        if not territory_id and not status:
            query = query.join(TrademarkRegistration)
        query = query.where(TrademarkRegistration.renewal_status == renewal_status)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    result = await db.execute(count_query)
    total = result.scalar()

    # Paginate
    query = query.offset((page - 1) * page_size).limit(page_size)
    query = query.order_by(Trademark.name)

    result = await db.execute(query)
    trademarks = result.scalars().unique().all()

    pages = (total + page_size - 1) // page_size

    return TrademarkListResponse(
        items=trademarks,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/{trademark_id}", response_model=TrademarkResponse)
async def get_trademark(
    trademark_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Trademark:
    """Get a single trademark by ID."""
    query = (
        select(Trademark)
        .where(Trademark.id == trademark_id)
        .options(
            selectinload(Trademark.rights_holder),
            selectinload(Trademark.classes),
            selectinload(Trademark.registrations).selectinload(TrademarkRegistration.territory),
        )
    )

    result = await db.execute(query)
    trademark = result.scalar_one_or_none()

    if not trademark:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trademark not found",
        )

    return trademark


@router.post("", response_model=TrademarkResponse, status_code=status.HTTP_201_CREATED)
async def create_trademark(
    trademark_data: TrademarkCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
) -> Trademark:
    """Create a new trademark (admin only)."""
    # Validate rights holder
    if trademark_data.rights_holder_id:
        result = await db.execute(
            select(RightsHolder).where(RightsHolder.id == trademark_data.rights_holder_id)
        )
        if not result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Rights holder not found",
            )

    # Create trademark
    trademark = Trademark(
        name=trademark_data.name,
        description=trademark_data.description,
        rights_holder_id=trademark_data.rights_holder_id,
    )
    db.add(trademark)
    await db.flush()

    # Add classes
    for class_num in trademark_data.classes:
        if 1 <= class_num <= 45:
            tm_class = TrademarkClass(
                trademark_id=trademark.id,
                icgs_class=class_num,
            )
            db.add(tm_class)

    # Add registrations
    for reg_data in trademark_data.registrations:
        # Validate territory
        result = await db.execute(
            select(Territory).where(Territory.id == reg_data.territory_id)
        )
        if not result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Territory {reg_data.territory_id} not found",
            )

        registration = TrademarkRegistration(
            trademark_id=trademark.id,
            territory_id=reg_data.territory_id,
            filing_date=reg_data.filing_date,
            priority_date=reg_data.priority_date,
            expiration_date=reg_data.expiration_date,
            application_number=reg_data.application_number,
            registration_number=reg_data.registration_number,
            is_national=reg_data.is_national,
            is_international=reg_data.is_international,
            madrid_registration_number=reg_data.madrid_registration_number,
            comments=reg_data.comments,
        )
        db.add(registration)

    await db.flush()

    # Reload with relationships
    query = (
        select(Trademark)
        .where(Trademark.id == trademark.id)
        .options(
            selectinload(Trademark.rights_holder),
            selectinload(Trademark.classes),
            selectinload(Trademark.registrations).selectinload(TrademarkRegistration.territory),
        )
    )
    result = await db.execute(query)
    return result.scalar_one()


@router.patch("/{trademark_id}", response_model=TrademarkResponse)
async def update_trademark(
    trademark_id: UUID,
    trademark_data: TrademarkUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
) -> Trademark:
    """Update a trademark (admin only)."""
    query = (
        select(Trademark)
        .where(Trademark.id == trademark_id)
        .options(
            selectinload(Trademark.rights_holder),
            selectinload(Trademark.classes),
            selectinload(Trademark.registrations).selectinload(TrademarkRegistration.territory),
        )
    )

    result = await db.execute(query)
    trademark = result.scalar_one_or_none()

    if not trademark:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trademark not found",
        )

    update_data = trademark_data.model_dump(exclude_unset=True)

    # Validate rights holder if updating
    if "rights_holder_id" in update_data and update_data["rights_holder_id"]:
        result = await db.execute(
            select(RightsHolder).where(RightsHolder.id == update_data["rights_holder_id"])
        )
        if not result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Rights holder not found",
            )

    for field, value in update_data.items():
        setattr(trademark, field, value)

    await db.flush()
    return trademark


@router.delete("/{trademark_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_trademark(
    trademark_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
) -> None:
    """Delete a trademark (admin only)."""
    result = await db.execute(select(Trademark).where(Trademark.id == trademark_id))
    trademark = result.scalar_one_or_none()

    if not trademark:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trademark not found",
        )

    await db.delete(trademark)


@router.get("/rights-holders/list", response_model=List[RightsHolderResponse])
async def list_rights_holders(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    search: Optional[str] = None,
) -> List[RightsHolder]:
    """List all rights holders."""
    query = select(RightsHolder)

    if search:
        query = query.where(RightsHolder.name.ilike(f"%{search}%"))

    query = query.order_by(RightsHolder.name)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/classes/list")
async def list_icgs_classes(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    """List all used ICGS classes with counts."""
    query = (
        select(
            TrademarkClass.icgs_class,
            TrademarkClass.product_group,
            func.count(TrademarkClass.id).label("count"),
        )
        .group_by(TrademarkClass.icgs_class, TrademarkClass.product_group)
        .order_by(TrademarkClass.icgs_class)
    )
    result = await db.execute(query)
    rows = result.all()

    return [
        {
            "icgs_class": row.icgs_class,
            "product_group": row.product_group,
            "count": row.count,
        }
        for row in rows
    ]


@router.get("/territories/list", response_model=List[TerritoryResponse])
async def list_territories(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    region: Optional[str] = None,
) -> List[Territory]:
    """List all territories."""
    query = select(Territory)

    if region:
        query = query.where(Territory.region == region)

    query = query.order_by(Territory.name_en)
    result = await db.execute(query)
    return result.scalars().all()

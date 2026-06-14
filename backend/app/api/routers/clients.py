from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from app.adapters.geocoder import get_geocoder
from app.api.deps import CurrentUser, SessionDep
from app.api.schemas import (
    AddressIn,
    AddressOut,
    AddressPatch,
    ClientDetailOut,
    ClientIn,
    ClientOut,
    ClientPatch,
    DuplicateGroupOut,
    GeocodeResponse,
    MergeRequest,
    MergeResultOut,
)
from app.core.enums import GeocodeStatus
from app.core.phones import normalize_phone
from app.models import Address, Client
from app.services.dedup import find_duplicate_groups, merge_clients
from app.services.geocoding import geocode_address

router = APIRouter(tags=["clients"])


def _address_from_in(client_id: int, body: AddressIn) -> Address:
    has_coords = body.latitude is not None and body.longitude is not None
    return Address(
        client_id=client_id,
        **body.model_dump(),
        geocode_status=GeocodeStatus.manual if has_coords else GeocodeStatus.none,
    )


@router.post("/clients", response_model=ClientDetailOut, status_code=201)
async def create_client(body: ClientIn, session: SessionDep, _: CurrentUser):
    client = Client(name=body.name, phone_primary=body.phone_primary, comment=body.comment)
    session.add(client)
    await session.flush()
    for addr in body.addresses:
        session.add(_address_from_in(client.id, addr))
    await session.commit()
    return await get_client(client.id, session, _)


@router.get("/clients", response_model=list[ClientOut])
async def search_clients(
    session: SessionDep,
    _: CurrentUser,
    q: str | None = Query(None, description="Подстрока имени или адреса"),
    phone: str | None = Query(None),
    limit: int = Query(50, le=200),
    offset: int = 0,
):
    # Слитые карточки (merged_into_id != null) в поиске не показываем
    query = select(Client).where(Client.merged_into_id.is_(None)).order_by(Client.id.desc())
    if q:
        query = query.outerjoin(Address).where(
            or_(Client.name.ilike(f"%{q}%"), Address.raw_address.ilike(f"%{q}%"))
        ).distinct()
    if phone:
        norm = normalize_phone(phone)
        # поиск по нормализованному (только цифры) — разделители не мешают
        query = query.where(Client.phone_normalized.like(f"%{norm or phone}%"))
    rows = await session.execute(query.limit(limit).offset(offset))
    return list(rows.scalars().all())


@router.get("/clients/duplicates", response_model=list[DuplicateGroupOut])
async def list_duplicates(session: SessionDep, _: CurrentUser):
    """Группы потенциальных дублей клиентов (по телефону/имени/адресу)."""
    return await find_duplicate_groups(session)


@router.post("/clients/merge", response_model=MergeResultOut)
async def merge_clients_endpoint(body: MergeRequest, session: SessionDep, _: CurrentUser):
    """Слить дубли в основную карточку: переносит адреса, контакты и заказы."""
    result = await merge_clients(session, body.target_id, body.source_ids)
    await session.commit()
    return result


@router.get("/clients/{client_id}", response_model=ClientDetailOut)
async def get_client(client_id: int, session: SessionDep, _: CurrentUser):
    client = (
        await session.execute(
            select(Client).where(Client.id == client_id).options(selectinload(Client.addresses))
        )
    ).scalar_one_or_none()
    if client is None:
        raise HTTPException(404, "Клиент не найден")
    return client


@router.patch("/clients/{client_id}", response_model=ClientOut)
async def patch_client(client_id: int, body: ClientPatch, session: SessionDep, _: CurrentUser):
    client = await session.get(Client, client_id)
    if client is None:
        raise HTTPException(404, "Клиент не найден")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(client, k, v)
    await session.commit()
    return client


@router.post("/clients/{client_id}/addresses", response_model=AddressOut, status_code=201)
async def add_address(client_id: int, body: AddressIn, session: SessionDep, _: CurrentUser):
    if await session.get(Client, client_id) is None:
        raise HTTPException(404, "Клиент не найден")
    address = _address_from_in(client_id, body)
    session.add(address)
    await session.commit()
    return address


@router.patch("/addresses/{address_id}", response_model=AddressOut)
async def patch_address(address_id: int, body: AddressPatch, session: SessionDep, _: CurrentUser):
    """Правка адреса, включая ручную правку координат и района."""
    address = await session.get(Address, address_id)
    if address is None:
        raise HTTPException(404, "Адрес не найден")
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(address, k, v)
    if "latitude" in data or "longitude" in data:
        if address.latitude is not None and address.longitude is not None:
            address.geocode_status = GeocodeStatus.manual
        else:
            address.geocode_status = GeocodeStatus.none
    await session.commit()
    return address


@router.post("/addresses/{address_id}/geocode", response_model=GeocodeResponse)
async def geocode_address_endpoint(
    address_id: int,
    session: SessionDep,
    _: CurrentUser,
    force: bool = False,
):
    """Геокодинг адреса через Яндекс (MVP-2). force=1 — перегеокодировать,
    несмотря на уже имеющиеся/ручные координаты."""
    address = await session.get(Address, address_id)
    if address is None:
        raise HTTPException(404, "Адрес не найден")
    provider = get_geocoder()
    if provider is None:
        raise HTTPException(503, "Геокодер не настроен (нет YANDEX_GEOCODER_API_KEY)")
    result = await geocode_address(session, address, provider, force=force)
    await session.commit()
    return result

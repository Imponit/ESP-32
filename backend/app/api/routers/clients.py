import re

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, SessionDep
from app.api.schemas import (
    AddressIn,
    AddressOut,
    AddressPatch,
    ClientDetailOut,
    ClientIn,
    ClientOut,
    ClientPatch,
)
from app.core.enums import GeocodeStatus
from app.models import Address, Client

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
    query = select(Client).order_by(Client.id.desc())
    if q:
        query = query.outerjoin(Address).where(
            or_(Client.name.ilike(f"%{q}%"), Address.raw_address.ilike(f"%{q}%"))
        ).distinct()
    if phone:
        digits = re.sub(r"\D", "", phone)
        query = query.where(Client.phone_primary.like(f"%{digits[-7:] if digits else phone}%"))
    rows = await session.execute(query.limit(limit).offset(offset))
    return list(rows.scalars().all())


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


# TODO MVP-2: POST /addresses/{id}/geocode — геокодинг через GeocoderProvider

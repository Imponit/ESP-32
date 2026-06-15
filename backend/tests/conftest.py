"""Фикстуры тестов: in-memory SQLite (продакшен — PostgreSQL, см. ASSUMPTIONS №20)."""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.enums import GeocodeStatus
from app.models import Address, Base, Client, District, Driver


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()


@pytest.fixture
async def fixtures(session):
    """Район, клиент с адресом (с координатами), водитель."""
    district = District(name="Центральный", sort_order=1)
    session.add(district)
    await session.flush()
    client = Client(name="Иван Петров", phone_primary="+7 900 111-22-33")
    session.add(client)
    await session.flush()
    address = Address(
        client_id=client.id,
        raw_address="пр. Мира, 12, кв. 5",
        latitude=Decimal("47.097133"),
        longitude=Decimal("37.543367"),
        geocode_status=GeocodeStatus.manual,
        district_id=district.id,
        entrance="2",
        floor="3",
    )
    driver = Driver(name="Сергей", phone="+7 900 555-66-77", capacity_bottles=40)
    session.add_all([address, driver])
    await session.flush()
    return {"district": district, "client": client, "address": address, "driver": driver}


def order_payload(fx, **overrides) -> dict:
    data = {
        "client_id": fx["client"].id,
        "address_id": fx["address"].id,
        "delivery_date": date.today(),
        "bottles_pc_qty": 2,
        "bottles_pet_qty": 0,
        "pumps_qty": 0,
        "total_amount": Decimal("600.00"),
    }
    data.update(overrides)
    return data

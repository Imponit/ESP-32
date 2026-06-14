"""Дедупликация клиентов (MVP-2): поиск дублей по телефону/имени/адресу,
слияние карточек с переносом адресов/контактов/заказов, исключение слитых."""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.models import Address, Client, ClientContact, Order
from app.services import orders as orders_service
from app.services.dedup import find_duplicate_groups, merge_clients
from app.services.errors import NotFoundError, ValidationError


async def _client(session, name, phone, address=None):
    c = Client(name=name, phone_primary=phone)
    session.add(c)
    await session.flush()
    if address:
        session.add(Address(client_id=c.id, raw_address=address))
        await session.flush()
    return c


async def test_find_duplicates_by_phone(session):
    await _client(session, "Иван", "+7 900 111-22-33")
    await _client(session, "Иван П.", "8 (900) 111-22-33")  # тот же номер иначе записан
    await _client(session, "Пётр", "+7 900 999-88-77")

    groups = await find_duplicate_groups(session)
    assert len(groups) == 1
    assert "одинаковый телефон" in groups[0]["reasons"]
    assert len(groups[0]["client_ids"]) == 2


async def test_find_duplicates_by_name_and_address(session):
    await _client(session, "Магазин Родник", "+7 900 000-00-01", "ул. Куприна 3")
    await _client(session, "магазин  родник", "+7 900 000-00-02", "ул. Куприна 3")

    groups = await find_duplicate_groups(session)
    assert len(groups) == 1
    g = groups[0]
    assert set(g["reasons"]) == {"совпадает имя", "общий адрес"}


async def test_no_false_positives(session):
    await _client(session, "Анна", "+7 900 111-11-11", "ул. A 1")
    await _client(session, "Борис", "+7 900 222-22-22", "ул. B 2")
    assert await find_duplicate_groups(session) == []


async def test_merge_moves_orders_addresses_contacts(session):
    target = await _client(session, "Иван", "+7 900 111-22-33", "Мира 12")
    source = await _client(session, "Иван П.", "+7 900 444-55-66", "Ленина 4")
    session.add(ClientContact(client_id=source.id, type="phone", value="+7 900 777-77-77"))
    await session.flush()
    src_addr = (
        await session.execute(select(Address).where(Address.client_id == source.id))
    ).scalar_one()
    # заказ на источнике
    order = await orders_service.create_order(
        session,
        {
            "client_id": source.id,
            "address_id": src_addr.id,
            "delivery_date": date.today(),
            "total_amount": Decimal("300.00"),
        },
        actor_id=1,
    )

    result = await merge_clients(session, target.id, [source.id])
    assert result["target_id"] == target.id
    assert result["moved"]["orders"] == 1
    assert result["moved"]["addresses"] == 1

    await session.refresh(source)
    assert source.merged_into_id == target.id
    # заказ и адрес теперь у target
    assert (await session.get(Order, order.id)).client_id == target.id
    addr_owners = (
        await session.execute(select(Address.client_id))
    ).scalars().all()
    assert all(o == target.id for o in addr_owners)
    # телефон источника сохранён контактом у target
    contacts = (
        await session.execute(select(ClientContact).where(ClientContact.client_id == target.id))
    ).scalars().all()
    values = {_digits(c.value) for c in contacts}
    assert _digits("+7 900 444-55-66") in values


async def test_merged_client_hidden_from_duplicates(session):
    target = await _client(session, "Иван", "+7 900 111-22-33")
    source = await _client(session, "Иван", "+7 900 111-22-33")  # дубль по телефону и имени
    assert len(await find_duplicate_groups(session)) == 1

    await merge_clients(session, target.id, [source.id])
    # после слияния группа исчезает — источник скрыт
    assert await find_duplicate_groups(session) == []


async def test_merge_validation(session):
    a = await _client(session, "A", "+7 900 000-00-01")
    with pytest.raises(ValidationError, match="среди сливаемых"):
        await merge_clients(session, a.id, [a.id])
    with pytest.raises(ValidationError, match="Не указаны"):
        await merge_clients(session, a.id, [])
    with pytest.raises(NotFoundError):
        await merge_clients(session, a.id, [99999])


async def test_double_merge_blocked(session):
    target = await _client(session, "T", "+7 900 000-00-01")
    source = await _client(session, "S", "+7 900 000-00-02")
    await merge_clients(session, target.id, [source.id])
    # повторное слияние уже слитого источника запрещено
    with pytest.raises(NotFoundError):
        await merge_clients(session, target.id, [source.id])
    assert await _count(session, Client) == 2  # карточки не удаляются


async def _count(session, model) -> int:
    return (await session.execute(select(func.count()).select_from(model))).scalar_one()


def _digits(s):
    import re

    return re.sub(r"\D", "", s)

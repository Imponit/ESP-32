"""Каталог товаров и позиции заказа (MVP-3)."""

from decimal import Decimal

import pytest
from sqlalchemy import select

from app.core.enums import ProductKind
from app.models import Product
from app.services import orders as orders_service
from app.services.errors import NotFoundError
from app.services.order_items import list_order_items
from tests.conftest import order_payload


async def _catalog(session):
    session.add_all([
        Product(name="Поликарбонат", kind=ProductKind.bottle_pc, unit_price=Decimal("300.00"),
                sort_order=1),
        Product(name="ПЭТ", kind=ProductKind.bottle_pet, unit_price=Decimal("250.00"),
                sort_order=2),
        Product(name="Помпа", kind=ProductKind.pump, unit_price=Decimal("1000.00"), sort_order=3),
    ])
    await session.flush()


async def test_items_built_from_quantities(session, fixtures):
    await _catalog(session)
    # order_payload по умолчанию: 2 ПК, 0 ПЭТ, total 600 (задан явно)
    order = await orders_service.create_order(session, order_payload(fixtures), actor_id=1)
    items = await list_order_items(session, order.id)
    assert len(items) == 1
    assert items[0].kind == ProductKind.bottle_pc
    assert items[0].qty == 2
    assert items[0].unit_price == Decimal("300.00")
    assert items[0].amount == Decimal("600.00")
    # total задан явно -> не пересчитываем
    assert order.total_amount == Decimal("600.00")


async def test_total_computed_from_catalog_when_not_given(session, fixtures):
    await _catalog(session)
    data = order_payload(
        fixtures, total_amount=Decimal("0.00"), bottles_pc_qty=2, bottles_pet_qty=1
    )
    order = await orders_service.create_order(session, data, actor_id=1)
    # 2*300 + 1*250 = 850
    assert order.total_amount == Decimal("850.00")
    items = await list_order_items(session, order.id)
    assert {i.kind for i in items} == {ProductKind.bottle_pc, ProductKind.bottle_pet}


async def test_items_without_catalog_price_zero(session, fixtures):
    # каталога нет — позиции создаются с ценой 0, total остаётся заданным
    order = await orders_service.create_order(session, order_payload(fixtures), actor_id=1)
    items = await list_order_items(session, order.id)
    assert len(items) == 1
    assert items[0].unit_price == Decimal("0.00")
    assert order.total_amount == Decimal("600.00")  # явно заданный


async def test_explicit_items_drive_quantities_and_total(session, fixtures):
    await _catalog(session)
    pc = (
        await session.execute(select(Product).where(Product.kind == ProductKind.bottle_pc))
    ).scalar_one()
    data = order_payload(fixtures, bottles_pc_qty=0, total_amount=Decimal("0.00"))
    data["items"] = [
        {"product_id": pc.id, "qty": 3},
        {"name": "Стакан", "kind": "other", "qty": 5, "unit_price": "10.00"},
    ]
    order = await orders_service.create_order(session, data, actor_id=1)
    items = await list_order_items(session, order.id)
    assert len(items) == 2
    # количество ПК выведено из позиций
    assert order.bottles_pc_qty == 3
    # сумма = 3*300 + 5*10 = 950
    assert order.total_amount == Decimal("950.00")
    other = [i for i in items if i.kind == ProductKind.other][0]
    assert other.name == "Стакан"
    assert other.amount == Decimal("50.00")


async def test_explicit_item_unknown_product(session, fixtures):
    data = order_payload(fixtures)
    data["items"] = [{"product_id": 99999, "qty": 1}]
    with pytest.raises(NotFoundError):
        await orders_service.create_order(session, data, actor_id=1)

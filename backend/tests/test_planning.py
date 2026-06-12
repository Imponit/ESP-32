"""Формирование пакета: лимит точек, валидации, route_url, предупреждение о вместимости."""

from datetime import date

import pytest

from app.core.enums import BatchStatus, DayPart, OrderStatus
from app.services import orders as orders_service
from app.services.errors import ValidationError
from app.services.planning import create_batch


async def make_assigned_orders(session, fx, count: int):
    from tests.conftest import order_payload

    result = []
    for _ in range(count):
        order = await orders_service.create_order(session, order_payload(fx), actor_id=None)
        await orders_service.assign_driver(session, order, fx["driver"].id, actor_id=None)
        result.append(order)
    return result


async def test_create_batch_happy_path(session, fixtures):
    orders = await make_assigned_orders(session, fixtures, 3)
    batch, warnings = await create_batch(
        session,
        delivery_date=date.today(),
        day_part=DayPart.first_half,
        district_id=fixtures["district"].id,
        driver_id=fixtures["driver"].id,
        order_ids=[o.id for o in orders],
    )
    assert batch.status == BatchStatus.draft
    assert warnings == []
    assert batch.route_url is not None and "rtt=auto" in batch.route_url
    # порядок диспетчера сохранён
    for pos, o in enumerate(orders, start=1):
        assert o.route_batch_id == batch.id
        assert o.route_position == pos


async def test_batch_respects_max_route_points(session, fixtures):
    orders = await make_assigned_orders(session, fixtures, 10)  # лимит по умолчанию — 9
    with pytest.raises(ValidationError, match="не больше 9"):
        await create_batch(
            session,
            delivery_date=date.today(),
            day_part=DayPart.any,
            district_id=None,
            driver_id=fixtures["driver"].id,
            order_ids=[o.id for o in orders],
        )


async def test_batch_capacity_warning_not_blocking(session, fixtures):
    fixtures["driver"].capacity_bottles = 3
    orders = await make_assigned_orders(session, fixtures, 2)  # 2 заказа × 2 бутыли = 4 > 3
    batch, warnings = await create_batch(
        session,
        delivery_date=date.today(),
        day_part=DayPart.any,
        district_id=None,
        driver_id=fixtures["driver"].id,
        order_ids=[o.id for o in orders],
    )
    assert batch.id is not None  # пакет создан, несмотря на предупреждение
    assert len(warnings) == 1 and "вместимости" in warnings[0]


async def test_batch_requires_assigned_status(session, fixtures):
    from tests.conftest import order_payload

    order = await orders_service.create_order(session, order_payload(fixtures), actor_id=None)
    assert order.status == OrderStatus.new
    with pytest.raises(ValidationError, match="не в статусе assigned"):
        await create_batch(
            session,
            delivery_date=date.today(),
            day_part=DayPart.any,
            district_id=None,
            driver_id=fixtures["driver"].id,
            order_ids=[order.id],
        )


async def test_order_not_in_two_batches(session, fixtures):
    orders = await make_assigned_orders(session, fixtures, 1)
    await create_batch(
        session,
        delivery_date=date.today(),
        day_part=DayPart.any,
        district_id=None,
        driver_id=fixtures["driver"].id,
        order_ids=[orders[0].id],
    )
    with pytest.raises(ValidationError, match="уже в пакете"):
        await create_batch(
            session,
            delivery_date=date.today(),
            day_part=DayPart.any,
            district_id=None,
            driver_id=fixtures["driver"].id,
            order_ids=[orders[0].id],
        )

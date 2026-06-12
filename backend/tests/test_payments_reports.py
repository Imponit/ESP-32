"""Фиксация оплаты и дневной отчёт/касса — сквозной доменный сценарий."""

from datetime import date
from decimal import Decimal

import pytest

from app.adapters.telegram import MockTelegramClient
from app.core.enums import (
    ActorType,
    BatchStatus,
    DayPart,
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
    WorkStatus,
)
from app.services import driver_actions
from app.services import orders as orders_service
from app.services.dispatch import send_batch
from app.services.errors import ValidationError
from app.services.payments import register_payment
from app.services.planning import create_batch
from app.services.reporting import daily_report
from tests.conftest import order_payload


async def full_driver_flow(session, fx, *, amount=None, method=PaymentMethod.cash):
    """Заказ проходит: new → ... → completed с оплатой, как в сценарии приёмки."""
    order = await orders_service.create_order(session, order_payload(fx), actor_id=1)
    await orders_service.assign_driver(session, order, fx["driver"].id, actor_id=1)
    batch, _ = await create_batch(
        session,
        delivery_date=date.today(),
        day_part=DayPart.first_half,
        district_id=fx["district"].id,
        driver_id=fx["driver"].id,
        order_ids=[order.id],
    )
    telegram = MockTelegramClient()
    await send_batch(session, batch, telegram)
    assert batch.status == BatchStatus.sent
    assert order.status == OrderStatus.sent_to_driver
    assert len(telegram.sent) == 1

    driver = fx["driver"]
    await driver_actions.batch_accept(session, batch, driver)
    assert order.status == OrderStatus.accepted_by_driver
    await driver_actions.batch_start(session, batch, driver)
    assert order.status == OrderStatus.in_progress
    assert driver.work_status == WorkStatus.on_route

    await driver_actions.order_complete(session, driver, order, method, amount)
    await driver_actions.batch_finish(session, batch, driver)
    assert driver.work_status == WorkStatus.idle
    return order, batch, telegram


async def test_payment_full_amount_marks_paid(session, fixtures):
    order, _, _ = await full_driver_flow(session, fixtures)
    assert order.status == OrderStatus.completed
    assert order.completed_at is not None
    assert order.paid_amount == Decimal("600.00")  # сумма по умолчанию = total_amount
    assert order.payment_status == PaymentStatus.paid


async def test_partial_payment(session, fixtures):
    order, _, _ = await full_driver_flow(session, fixtures, amount=Decimal("400.00"))
    assert order.payment_status == PaymentStatus.partial
    assert order.paid_amount == Decimal("400.00")


async def test_payment_rejects_non_positive(session, fixtures):
    order = await orders_service.create_order(session, order_payload(fixtures), actor_id=1)
    with pytest.raises(ValidationError):
        await register_payment(
            session, order, PaymentMethod.cash, Decimal("0.00"), ActorType.dispatcher
        )


async def test_daily_report_and_driver_cash(session, fixtures):
    order, _, _ = await full_driver_flow(session, fixtures)
    report = await daily_report(session, date.today())

    assert report["orders_by_status"]["completed"] == 1
    assert report["bottles_delivered"]["pc"] == 2
    assert report["money_by_method"]["cash"] == Decimal("600.00")
    assert report["completed_unpaid_order_ids"] == []

    drv = report["drivers"][0]
    assert drv["driver_id"] == fixtures["driver"].id
    assert drv["completed_orders"] == 1
    assert drv["bottles"] == 2
    assert drv["cash"] == Decimal("600.00")
    assert drv["cashless"] == Decimal("0.00")


async def test_report_shows_completed_without_payment(session, fixtures):
    order, _, _ = await full_driver_flow(session, fixtures, method=None)
    report = await daily_report(session, date.today())
    assert report["completed_unpaid_order_ids"] == [order.id]
    assert report["money_by_method"] == {}


async def test_report_refused_with_reason(session, fixtures):
    order = await orders_service.create_order(session, order_payload(fixtures), actor_id=1)
    await orders_service.assign_driver(session, order, fixtures["driver"].id, actor_id=1)
    batch, _ = await create_batch(
        session, date.today(), DayPart.any, None, fixtures["driver"].id, [order.id]
    )
    await send_batch(session, batch, MockTelegramClient())
    driver = fixtures["driver"]
    await driver_actions.batch_accept(session, batch, driver)
    await driver_actions.batch_start(session, batch, driver)
    await driver_actions.order_refuse(session, driver, order, "клиент передумал")

    report = await daily_report(session, date.today())
    assert report["refused_orders"] == [{"order_id": order.id, "reason": "клиент передумал"}]

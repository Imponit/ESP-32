"""Отметка «водитель сдал кассу» (MVP-2, раздел 13)."""

from datetime import date
from decimal import Decimal

import pytest

from app.adapters.telegram import MockTelegramClient
from app.core.enums import DayPart, PaymentMethod
from app.services import driver_actions
from app.services import orders as orders_service
from app.services.cash import handovers_for_date, mark_cash_handover, remove_cash_handover
from app.services.dispatch import send_batch
from app.services.errors import NotFoundError
from app.services.planning import create_batch
from app.services.reporting import daily_report
from tests.conftest import order_payload


async def test_mark_and_query_handover(session, fixtures):
    driver = fixtures["driver"]
    today = date.today()
    row = await mark_cash_handover(session, driver.id, today, Decimal("600.00"), "сдал вечером", 1)
    assert row.id is not None

    handovers = await handovers_for_date(session, today)
    assert driver.id in handovers
    assert handovers[driver.id].amount == Decimal("600.00")


async def test_mark_is_idempotent_upsert(session, fixtures):
    driver = fixtures["driver"]
    today = date.today()
    await mark_cash_handover(session, driver.id, today, Decimal("500.00"), None, 1)
    await mark_cash_handover(session, driver.id, today, Decimal("650.00"), "пересдал", 1)

    rows = (await handovers_for_date(session, today))
    assert len(rows) == 1  # одна запись на (водитель, дата)
    assert rows[driver.id].amount == Decimal("650.00")
    assert rows[driver.id].comment == "пересдал"


async def test_remove_handover(session, fixtures):
    driver = fixtures["driver"]
    today = date.today()
    await mark_cash_handover(session, driver.id, today, None, None, 1)
    assert await remove_cash_handover(session, driver.id, today) is True
    assert await remove_cash_handover(session, driver.id, today) is False  # уже нет
    assert await handovers_for_date(session, today) == {}


async def test_mark_unknown_driver(session, fixtures):
    with pytest.raises(NotFoundError):
        await mark_cash_handover(session, 99999, date.today(), None, None, 1)


async def test_daily_report_shows_handover_flag(session, fixtures):
    driver = fixtures["driver"]
    today = date.today()
    # выполненный заказ, чтобы водитель попал в кассовую часть отчёта
    order = await orders_service.create_order(session, order_payload(fixtures), actor_id=1)
    await orders_service.assign_driver(session, order, driver.id, actor_id=1)
    batch, _ = await create_batch(
        session, today, DayPart.first_half, fixtures["district"].id, driver.id, [order.id]
    )
    await send_batch(session, batch, MockTelegramClient())
    await driver_actions.batch_accept(session, batch, driver)
    await driver_actions.batch_start(session, batch, driver)
    await driver_actions.order_complete(session, driver, order, PaymentMethod.cash, None)

    # до отметки — не сдал
    report = await daily_report(session, today)
    assert report["drivers"][0]["cash_handed_over"] is False
    assert report["drivers"][0]["handover_amount"] is None

    # после отметки — сдал, с суммой
    await mark_cash_handover(session, driver.id, today, Decimal("600.00"), None, 1)
    report2 = await daily_report(session, today)
    assert report2["drivers"][0]["cash_handed_over"] is True
    assert report2["drivers"][0]["handover_amount"] == "600.00"

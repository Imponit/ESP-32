"""Аналитика за период (MVP-3): KPI и разбивки."""

from datetime import date
from decimal import Decimal

from app.core.analytics import build_analytics
from app.core.enums import OrderStatus, PaymentMethod, ProductKind


class ORow:
    def __init__(self, id, status, day, district=1, driver=7, pc=2, pet=0, pumps=0, total="600"):
        self.id = id
        self.status = status
        self.delivery_date = day
        self.district_id = district
        self.assigned_driver_id = driver
        self.bottles_pc_qty = pc
        self.bottles_pet_qty = pet
        self.pumps_qty = pumps
        self.total_amount = Decimal(total)


class PRow:
    def __init__(self, order_id, driver, method, amount):
        self.order_id = order_id
        self.driver_id = driver
        self.method = method
        self.amount = Decimal(amount)


class IRow:
    def __init__(self, order_id, name, kind, qty, amount):
        self.order_id = order_id
        self.name = name
        self.kind = kind
        self.qty = qty
        self.amount = Decimal(amount)


D1 = date(2026, 6, 20)
D2 = date(2026, 6, 21)
NAMES = {7: "Сергей", 8: "Андрей"}
DISTRICTS = {1: "Центральный", 2: "Приморский"}


def test_kpis_and_rates():
    orders = [
        ORow(1, OrderStatus.completed, D1),
        ORow(2, OrderStatus.completed, D1),
        ORow(3, OrderStatus.failed, D1),
        ORow(4, OrderStatus.refused, D2),
        ORow(5, OrderStatus.new, D2),
    ]
    payments = [PRow(1, 7, PaymentMethod.cash, "600"), PRow(2, 7, PaymentMethod.cashless, "600")]
    items = [IRow(1, "Вода ПК", ProductKind.bottle_pc, 2, "600"),
             IRow(2, "Вода ПК", ProductKind.bottle_pc, 2, "600")]
    r = build_analytics(orders, payments, items, NAMES, DISTRICTS)

    assert r["orders_total"] == 5
    assert r["completed"] == 2
    assert r["failed"] == 1
    assert r["refused"] == 1
    assert r["fill_rate"] == 40.0  # 2/5
    assert r["failure_rate"] == 20.0
    assert r["refusal_rate"] == 20.0
    assert r["bottles"]["total"] == 4  # только выполненные
    assert r["revenue_collected"] == Decimal("1200")
    assert r["money_by_method"]["cash"] == Decimal("600")
    assert r["avg_order_value"] == Decimal("600.00")


def test_by_day_grouping():
    orders = [ORow(1, OrderStatus.completed, D1), ORow(2, OrderStatus.completed, D2)]
    payments = [PRow(1, 7, PaymentMethod.cash, "600"), PRow(2, 7, PaymentMethod.cash, "300")]
    r = build_analytics(orders, payments, [], NAMES, DISTRICTS)
    assert [d["date"] for d in r["by_day"]] == [D1.isoformat(), D2.isoformat()]
    assert r["by_day"][0]["revenue"] == Decimal("600")
    assert r["by_day"][1]["revenue"] == Decimal("300")


def test_by_driver_and_district():
    orders = [
        ORow(1, OrderStatus.completed, D1, district=1, driver=7),
        ORow(2, OrderStatus.completed, D1, district=2, driver=8),
        ORow(3, OrderStatus.failed, D1, district=1, driver=7),
    ]
    payments = [PRow(1, 7, PaymentMethod.cash, "600"), PRow(2, 8, PaymentMethod.cashless, "300")]
    r = build_analytics(orders, payments, [], NAMES, DISTRICTS)

    drv7 = [d for d in r["by_driver"] if d["driver_id"] == 7][0]
    assert drv7["completed"] == 1
    assert drv7["failed"] == 1
    assert drv7["cash"] == Decimal("600")

    # районы отсортированы по выручке: Центральный(600) > Приморский(300)
    assert r["by_district"][0]["district_name"] == "Центральный"
    assert r["by_district"][0]["revenue"] == Decimal("600")


def test_top_products_sorted_by_amount():
    items = [
        IRow(1, "Помпа", ProductKind.pump, 1, "1000"),
        IRow(1, "Вода ПК", ProductKind.bottle_pc, 2, "600"),
        IRow(2, "Вода ПК", ProductKind.bottle_pc, 3, "900"),
    ]
    orders = [ORow(1, OrderStatus.completed, D1), ORow(2, OrderStatus.completed, D1)]
    r = build_analytics(orders, [], items, NAMES, DISTRICTS)
    top = r["top_products"]
    assert top[0]["name"] == "Вода ПК"  # 600+900=1500
    assert top[0]["qty"] == 5
    assert top[0]["amount"] == Decimal("1500")
    assert top[1]["name"] == "Помпа"


def test_empty_period_no_division_error():
    r = build_analytics([], [], [], NAMES, DISTRICTS)
    assert r["orders_total"] == 0
    assert r["fill_rate"] == 0.0
    assert r["avg_order_value"] == Decimal("0.00")
    assert r["by_day"] == []
    assert r["top_products"] == []


# --- интеграция с БД ---


async def test_period_analytics_db(session, fixtures):
    from app.adapters.telegram import MockTelegramClient
    from app.core.enums import DayPart
    from app.services import driver_actions
    from app.services import orders as orders_service
    from app.services.analytics import period_analytics
    from app.services.dispatch import send_batch
    from app.services.planning import create_batch
    from tests.conftest import order_payload

    order = await orders_service.create_order(session, order_payload(fixtures), actor_id=1)
    await orders_service.assign_driver(session, order, fixtures["driver"].id, actor_id=1)
    batch, _ = await create_batch(
        session, date.today(), DayPart.any, None, fixtures["driver"].id, [order.id]
    )
    await send_batch(session, batch, MockTelegramClient())
    driver = fixtures["driver"]
    await driver_actions.batch_accept(session, batch, driver)
    await driver_actions.batch_start(session, batch, driver)
    await driver_actions.order_complete(session, driver, order, PaymentMethod.cash, None)

    r = await period_analytics(session, date.today(), date.today())
    assert r["completed"] == 1
    assert r["fill_rate"] == 100.0
    assert r["revenue_collected"] == Decimal("600.00")
    assert r["by_driver"][0]["driver_name"] == "Сергей"

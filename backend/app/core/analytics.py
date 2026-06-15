"""Расчёт аналитики за период (SPEC.md, раздел 3 MVP-3, п.5). Чистая логика, без БД.

Считает сводные KPI и разбивки (по дням / водителям / районам / товарам) из строк
заказов, оплат и позиций. Деньги — Decimal; доли — проценты, округлённые до 0.1.
"""

from collections import defaultdict
from decimal import Decimal
from typing import Any

from app.core.enums import OrderStatus

_ZERO = Decimal("0.00")


def _pct(part: int, whole: int) -> float:
    return round(100.0 * part / whole, 1) if whole else 0.0


def _driver_row(driver_id: int, name: str) -> dict:
    return {
        "driver_id": driver_id,
        "driver_name": name,
        "completed": 0,
        "bottles": 0,
        "cash": _ZERO,
        "cashless": _ZERO,
        "failed": 0,
        "refused": 0,
    }


def build_analytics(
    orders: list[Any],
    payments: list[Any],
    items: list[Any],
    driver_names: dict[int, str],
    district_names: dict[int, str],
) -> dict:
    """orders/payments/items — строки за период. items — позиции выполненных заказов."""
    order_by_id = {o.id: o for o in orders}

    by_status: dict[str, int] = defaultdict(int)
    for o in orders:
        by_status[o.status.value] += 1
    total = len(orders)
    completed_orders = [o for o in orders if o.status == OrderStatus.completed]
    completed = len(completed_orders)
    failed = by_status.get(OrderStatus.failed.value, 0)
    refused = by_status.get(OrderStatus.refused.value, 0)

    bottles_pc = sum(o.bottles_pc_qty for o in completed_orders)
    bottles_pet = sum(o.bottles_pet_qty for o in completed_orders)
    pumps = sum(o.pumps_qty for o in completed_orders)

    money_by_method: dict[str, Decimal] = defaultdict(lambda: _ZERO)
    revenue_collected = _ZERO
    for p in payments:
        money_by_method[p.method.value] += p.amount
        revenue_collected += p.amount

    completed_value = sum((o.total_amount for o in completed_orders), _ZERO)
    avg_order_value = (
        (completed_value / completed).quantize(Decimal("0.01")) if completed else _ZERO
    )

    # По дням
    days: dict[Any, dict] = {}
    for o in orders:
        d = days.setdefault(
            o.delivery_date,
            {"date": o.delivery_date.isoformat(), "orders": 0, "completed": 0,
             "bottles": 0, "revenue": _ZERO},
        )
        d["orders"] += 1
        if o.status == OrderStatus.completed:
            d["completed"] += 1
            d["bottles"] += o.bottles_pc_qty + o.bottles_pet_qty
    for p in payments:
        o = order_by_id.get(p.order_id)
        if o is not None and o.delivery_date in days:
            days[o.delivery_date]["revenue"] += p.amount
    by_day = [days[k] for k in sorted(days)]

    # По водителям
    drivers: dict[int, dict] = {}
    for o in completed_orders:
        if o.assigned_driver_id is None:
            continue
        row = drivers.setdefault(
            o.assigned_driver_id,
            _driver_row(o.assigned_driver_id, driver_names.get(o.assigned_driver_id, "?")),
        )
        row["completed"] += 1
        row["bottles"] += o.bottles_pc_qty + o.bottles_pet_qty
    for o in orders:
        if o.assigned_driver_id is None:
            continue
        if o.status in (OrderStatus.failed, OrderStatus.refused):
            row = drivers.setdefault(
                o.assigned_driver_id,
                _driver_row(o.assigned_driver_id, driver_names.get(o.assigned_driver_id, "?")),
            )
            row["failed" if o.status == OrderStatus.failed else "refused"] += 1
    for p in payments:
        if p.driver_id is None:
            continue
        row = drivers.setdefault(
            p.driver_id, _driver_row(p.driver_id, driver_names.get(p.driver_id, "?"))
        )
        if p.method.value in ("cash", "cashless"):
            row[p.method.value] += p.amount
    by_driver = sorted(drivers.values(), key=lambda r: (-r["completed"], r["driver_id"]))

    # По районам
    districts: dict[Any, dict] = {}
    for o in orders:
        row = districts.setdefault(
            o.district_id,
            {"district_id": o.district_id,
             "district_name": district_names.get(o.district_id, "—"),
             "orders": 0, "completed": 0, "bottles": 0, "revenue": _ZERO},
        )
        row["orders"] += 1
        if o.status == OrderStatus.completed:
            row["completed"] += 1
            row["bottles"] += o.bottles_pc_qty + o.bottles_pet_qty
    for p in payments:
        o = order_by_id.get(p.order_id)
        if o is not None and o.district_id in districts:
            districts[o.district_id]["revenue"] += p.amount
    by_district = sorted(districts.values(), key=lambda r: -r["revenue"])

    # Топ товаров (по позициям выполненных заказов)
    products: dict[str, dict] = {}
    for it in items:
        row = products.setdefault(it.name, {"name": it.name, "qty": 0, "amount": _ZERO})
        row["qty"] += it.qty
        row["amount"] += it.amount
    top_products = sorted(products.values(), key=lambda r: -r["amount"])

    return {
        "orders_total": total,
        "orders_by_status": dict(by_status),
        "completed": completed,
        "failed": failed,
        "refused": refused,
        "fill_rate": _pct(completed, total),
        "failure_rate": _pct(failed, total),
        "refusal_rate": _pct(refused, total),
        "bottles": {"pc": bottles_pc, "pet": bottles_pet, "total": bottles_pc + bottles_pet,
                    "pumps": pumps},
        "revenue_collected": revenue_collected,
        "money_by_method": dict(money_by_method),
        "completed_value": completed_value,
        "avg_order_value": avg_order_value,
        "by_day": by_day,
        "by_driver": by_driver,
        "by_district": by_district,
        "top_products": top_products,
    }

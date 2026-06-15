"""Расчёт дневного отчёта (SPEC.md, разделы 10/13). Чистая функция над строками данных.

Принимает упрощённые записи (duck typing: ORM-объекты или любые объекты с теми же
атрибутами), возвращает структуру отчёта. Запросы к БД — в services/reporting.py.
"""

from collections import defaultdict
from decimal import Decimal
from typing import Any, Protocol

from app.core.enums import OrderStatus, PaymentMethod


class OrderRow(Protocol):
    id: int
    status: OrderStatus
    bottles_pc_qty: int
    bottles_pet_qty: int
    pumps_qty: int
    total_amount: Decimal
    paid_amount: Decimal
    assigned_driver_id: int | None


class PaymentRow(Protocol):
    order_id: int
    driver_id: int | None
    method: PaymentMethod
    amount: Decimal


def build_daily_report(
    orders: list[Any],
    payments: list[Any],
    driver_names: dict[int, str],
    refusal_reasons: dict[int, str] | None = None,
) -> dict:
    """Сводка дня: заказы по статусам, бутыли, деньги по способам оплаты,
    касса по водителям, отказы с причинами, completed без оплаты."""
    refusal_reasons = refusal_reasons or {}

    by_status: dict[str, int] = defaultdict(int)
    for o in orders:
        by_status[o.status.value] += 1

    completed = [o for o in orders if o.status == OrderStatus.completed]
    bottles = {
        "pc": sum(o.bottles_pc_qty for o in completed),
        "pet": sum(o.bottles_pet_qty for o in completed),
        "pumps": sum(o.pumps_qty for o in completed),
    }

    totals_by_method: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
    for p in payments:
        totals_by_method[p.method.value] += p.amount

    drivers: dict[int, dict] = {}
    for o in completed:
        if o.assigned_driver_id is None:
            continue
        d = drivers.setdefault(
            o.assigned_driver_id,
            {
                "driver_id": o.assigned_driver_id,
                "driver_name": driver_names.get(o.assigned_driver_id, "?"),
                "completed_orders": 0,
                "bottles": 0,
                "cash": Decimal("0.00"),
                "cashless": Decimal("0.00"),
                "other": Decimal("0.00"),
            },
        )
        d["completed_orders"] += 1
        d["bottles"] += o.bottles_pc_qty + o.bottles_pet_qty
    for p in payments:
        if p.driver_id is None:
            continue
        d = drivers.setdefault(
            p.driver_id,
            {
                "driver_id": p.driver_id,
                "driver_name": driver_names.get(p.driver_id, "?"),
                "completed_orders": 0,
                "bottles": 0,
                "cash": Decimal("0.00"),
                "cashless": Decimal("0.00"),
                "other": Decimal("0.00"),
            },
        )
        d[p.method.value] += p.amount

    refused = [
        {"order_id": o.id, "reason": refusal_reasons.get(o.id, "")}
        for o in orders
        if o.status == OrderStatus.refused
    ]
    completed_unpaid = [o.id for o in completed if o.paid_amount < o.total_amount]

    return {
        "orders_by_status": dict(by_status),
        "orders_total": len(orders),
        "bottles_delivered": bottles,
        "money_by_method": {k: v for k, v in totals_by_method.items()},
        "drivers": sorted(drivers.values(), key=lambda d: d["driver_id"]),
        "refused_orders": refused,
        "completed_unpaid_order_ids": completed_unpaid,
    }

"""Аналитика за период: запросы к БД + чистый расчёт из app/core/analytics.py."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.analytics import build_analytics
from app.core.enums import OrderStatus
from app.models import District, Driver, Order, OrderItem, Payment


async def period_analytics(
    session: AsyncSession, date_from: date, date_to: date
) -> dict:
    orders = list(
        (
            await session.execute(
                select(Order).where(
                    Order.delivery_date >= date_from, Order.delivery_date <= date_to
                )
            )
        )
        .scalars()
        .all()
    )
    order_ids = [o.id for o in orders]
    completed_ids = [o.id for o in orders if o.status == OrderStatus.completed]

    payments = (
        list(
            (await session.execute(select(Payment).where(Payment.order_id.in_(order_ids))))
            .scalars()
            .all()
        )
        if order_ids
        else []
    )
    items = (
        list(
            (await session.execute(select(OrderItem).where(OrderItem.order_id.in_(completed_ids))))
            .scalars()
            .all()
        )
        if completed_ids
        else []
    )
    driver_names = {d.id: d.name for d in (await session.execute(select(Driver))).scalars().all()}
    district_names = {
        d.id: d.name for d in (await session.execute(select(District))).scalars().all()
    }

    report = build_analytics(orders, payments, items, driver_names, district_names)
    report["date_from"] = date_from.isoformat()
    report["date_to"] = date_to.isoformat()
    return report

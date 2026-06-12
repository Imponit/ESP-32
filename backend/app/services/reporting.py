"""Дневной отчёт: запросы к БД + чистый расчёт из app/core/reports.py."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import OrderStatus
from app.core.reports import build_daily_report
from app.models import Driver, Order, OrderEvent, Payment


async def daily_report(session: AsyncSession, report_date: date) -> dict:
    orders = list(
        (await session.execute(select(Order).where(Order.delivery_date == report_date)))
        .scalars()
        .all()
    )
    order_ids = [o.id for o in orders]
    payments = (
        list(
            (await session.execute(select(Payment).where(Payment.order_id.in_(order_ids))))
            .scalars()
            .all()
        )
        if order_ids
        else []
    )
    driver_names = {
        d.id: d.name for d in (await session.execute(select(Driver))).scalars().all()
    }
    # Причины отказов — из комментариев переходов в refused
    refusal_reasons: dict[int, str] = {}
    if order_ids:
        events = (
            await session.execute(
                select(OrderEvent)
                .where(
                    OrderEvent.order_id.in_(order_ids),
                    OrderEvent.new_status == OrderStatus.refused.value,
                )
                .order_by(OrderEvent.id)
            )
        ).scalars()
        for e in events:
            refusal_reasons[e.order_id] = e.comment or ""

    report = build_daily_report(orders, payments, driver_names, refusal_reasons)
    report["date"] = report_date.isoformat()
    return report

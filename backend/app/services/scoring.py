"""Баллы водителей (SPEC.md, раздел 14, MVP-2): запросы к БД + чистый расчёт.

Коэффициенты берутся из настройки `scoring_rules` (settings JSON), таймзона — из
настройки `timezone`. Расчёт всегда по orders/order_events; результат можно
сохранить снимком в driver_scores.
"""

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import OrderStatus
from app.core.scoring import compute_scores, merge_rules, to_decimal
from app.models import Driver, DriverScore, Order, OrderEvent
from app.services.app_settings import KEY_SCORING_RULES, get_setting, get_timezone


async def compute_driver_scores(
    session: AsyncSession,
    period_from: date,
    period_to: date,
    driver_id: int | None = None,
) -> list[dict]:
    """Баллы по каждому водителю за период [period_from, period_to] включительно."""
    rules = merge_rules(await get_setting(session, KEY_SCORING_RULES, None))
    tz = await get_timezone(session)

    q = select(Order).where(
        Order.delivery_date >= period_from,
        Order.delivery_date <= period_to,
        Order.assigned_driver_id.is_not(None),
    )
    if driver_id is not None:
        q = q.where(Order.assigned_driver_id == driver_id)
    orders = list((await session.execute(q)).scalars().all())

    order_ids = [o.id for o in orders]
    failed_has_reason: dict[int, bool] = {}
    if order_ids:
        events = (
            await session.execute(
                select(OrderEvent).where(
                    OrderEvent.order_id.in_(order_ids),
                    OrderEvent.new_status == OrderStatus.failed.value,
                )
            )
        ).scalars()
        for e in events:
            # причина есть, если комментарий перехода непустой
            failed_has_reason[e.order_id] = bool(e.comment and e.comment.strip())

    driver_names = {
        d.id: d.name for d in (await session.execute(select(Driver))).scalars().all()
    }
    return compute_scores(orders, failed_has_reason, driver_names, rules, tz)


async def save_driver_scores(
    session: AsyncSession, period_from: date, period_to: date
) -> list[DriverScore]:
    """Сохранить снимок баллов за период в driver_scores."""
    scores = await compute_driver_scores(session, period_from, period_to)
    rows = []
    for s in scores:
        row = DriverScore(
            driver_id=s["driver_id"],
            period_from=period_from,
            period_to=period_to,
            points=to_decimal(s["points"]),
            breakdown=s["breakdown"],
        )
        session.add(row)
        rows.append(row)
    await session.flush()
    return rows

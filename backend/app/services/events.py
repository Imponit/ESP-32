"""Журнал событий (SPEC.md, раздел 3 MVP-2): лента order_events с фильтрами.

Обогащаем каждое событие контекстом заказа (клиент, адрес) и именем актора
(диспетчер — из users, водитель — из drivers).
"""

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ActorType
from app.models import Driver, Order, OrderEvent, User


async def list_events(
    session: AsyncSession,
    date_from: date | None = None,
    date_to: date | None = None,
    order_id: int | None = None,
    actor_type: ActorType | None = None,
    event_type: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[dict], int]:
    q = select(OrderEvent)
    if date_from is not None:
        q = q.where(func.date(OrderEvent.created_at) >= date_from)
    if date_to is not None:
        q = q.where(func.date(OrderEvent.created_at) <= date_to)
    if order_id is not None:
        q = q.where(OrderEvent.order_id == order_id)
    if actor_type is not None:
        q = q.where(OrderEvent.actor_type == actor_type)
    if event_type is not None:
        q = q.where(OrderEvent.event_type == event_type)

    total = (
        await session.execute(q.with_only_columns(func.count(OrderEvent.id)))
    ).scalar_one()
    events = list(
        (await session.execute(q.order_by(OrderEvent.id.desc()).limit(limit).offset(offset)))
        .scalars()
        .all()
    )

    # Обогащение пакетно: заказы, имена диспетчеров и водителей
    order_ids = {e.order_id for e in events}
    orders = (
        {
            o.id: o
            for o in (
                await session.execute(select(Order).where(Order.id.in_(order_ids)))
            ).scalars()
        }
        if order_ids
        else {}
    )
    user_ids = {e.actor_id for e in events if e.actor_type == ActorType.dispatcher and e.actor_id}
    driver_ids = {e.actor_id for e in events if e.actor_type == ActorType.driver and e.actor_id}
    user_names = (
        {
            u.id: u.name
            for u in (
                await session.execute(select(User).where(User.id.in_(user_ids)))
            ).scalars()
        }
        if user_ids
        else {}
    )
    driver_names = (
        {
            d.id: d.name
            for d in (
                await session.execute(select(Driver).where(Driver.id.in_(driver_ids)))
            ).scalars()
        }
        if driver_ids
        else {}
    )

    def actor_name(e: OrderEvent) -> str:
        if e.actor_type == ActorType.dispatcher:
            return user_names.get(e.actor_id, "диспетчер")
        if e.actor_type == ActorType.driver:
            return driver_names.get(e.actor_id, "водитель")
        return "система"

    rows = []
    for e in events:
        o = orders.get(e.order_id)
        rows.append(
            {
                "id": e.id,
                "order_id": e.order_id,
                "event_type": e.event_type,
                "old_status": e.old_status,
                "new_status": e.new_status,
                "actor_type": e.actor_type.value,
                "actor_id": e.actor_id,
                "actor_name": actor_name(e),
                "comment": e.comment,
                "created_at": e.created_at,
                "order_client_name": o.client_name if o else None,
                "order_address": o.address_text if o else None,
            }
        )
    return rows, total

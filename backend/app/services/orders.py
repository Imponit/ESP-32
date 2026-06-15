"""Сервис заказов: создание со снапшотом, переходы статусов, назначение водителя.

Все смены статуса — только здесь, через машину состояний; каждый переход
пишет запись в order_events.
"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ActorType, OrderStatus
from app.core.state_machine import validate_transition
from app.models import Address, Client, Driver, Order, OrderEvent
from app.services.errors import NotFoundError, ValidationError


def _snapshot_from(client: Client, address: Address) -> dict:
    """Снапшот-поля заказа: копируются при создании и не меняются вслед за карточкой."""
    return {
        "phone": client.phone_primary,
        "client_name": client.name,
        "district_id": address.district_id,
        "entrance": address.entrance,
        "floor": address.floor,
        "address_text": address.raw_address,
    }


async def create_order(session: AsyncSession, data: dict, actor_id: int | None) -> Order:
    data = dict(data)
    items_data = data.pop("items", None)  # MVP-3: позиции заказа (необязательно)

    client = await session.get(Client, data["client_id"])
    if client is None:
        raise NotFoundError("Клиент не найден")
    address = await session.get(Address, data["address_id"])
    if address is None or address.client_id != client.id:
        raise NotFoundError("Адрес не найден или принадлежит другому клиенту")

    order = Order(**data, **_snapshot_from(client, address), status=OrderStatus.new)
    session.add(order)
    await session.flush()

    # Позиции заказа: из явных items или из количеств по каталогу (MVP-3)
    from app.services.order_items import build_items_for_order

    await build_items_for_order(session, order, items_data)

    session.add(
        OrderEvent(
            order_id=order.id,
            event_type="created",
            old_status=None,
            new_status=OrderStatus.new.value,
            actor_type=ActorType.dispatcher,
            actor_id=actor_id,
        )
    )
    await session.flush()
    return order


async def update_order(
    session: AsyncSession, order: Order, data: dict, actor_id: int | None
) -> Order:
    """Правка полей заказа (не статуса). При смене адреса снапшот перекопируется."""
    if "address_id" in data and data["address_id"] != order.address_id:
        address = await session.get(Address, data["address_id"])
        if address is None or address.client_id != order.client_id:
            raise NotFoundError("Адрес не найден или принадлежит другому клиенту")
        client = await session.get(Client, order.client_id)
        for k, v in _snapshot_from(client, address).items():
            setattr(order, k, v)
    for k, v in data.items():
        setattr(order, k, v)
    await session.flush()
    return order


async def transition_order(
    session: AsyncSession,
    order: Order,
    new_status: OrderStatus,
    actor_type: ActorType,
    actor_id: int | None = None,
    comment: str | None = None,
) -> Order:
    """Единственная точка смены статуса заказа."""
    old_status = order.status
    validate_transition(old_status, new_status, comment)

    if new_status == OrderStatus.assigned and order.assigned_driver_id is None:
        raise ValidationError("Нельзя перевести в assigned без назначенного водителя")
    if new_status == OrderStatus.completed:
        order.completed_at = datetime.now(UTC)
    if new_status in (OrderStatus.planned, OrderStatus.new) and old_status in (
        OrderStatus.assigned,
        OrderStatus.postponed,
    ):
        # снятие назначения / возврат переноса в работу
        order.assigned_driver_id = None
        order.route_batch_id = None
        order.route_position = None

    order.status = new_status
    session.add(
        OrderEvent(
            order_id=order.id,
            event_type="status_change",
            old_status=old_status.value,
            new_status=new_status.value,
            actor_type=actor_type,
            actor_id=actor_id,
            comment=comment,
        )
    )
    await session.flush()
    return order


async def assign_driver(
    session: AsyncSession, order: Order, driver_id: int | None, actor_id: int | None
) -> Order:
    """Назначение/снятие водителя. new -> planned -> assigned (оба перехода в order_events)."""
    if driver_id is None:
        return await transition_order(
            session, order, OrderStatus.planned, ActorType.dispatcher, actor_id
        )

    driver = await session.get(Driver, driver_id)
    if driver is None or not driver.is_active:
        raise NotFoundError("Водитель не найден или деактивирован")

    if order.status == OrderStatus.new:
        await transition_order(session, order, OrderStatus.planned, ActorType.dispatcher, actor_id)
    if order.status != OrderStatus.planned:
        raise ValidationError(f"Назначение возможно из planned/new, текущий: {order.status.value}")
    order.assigned_driver_id = driver_id
    return await transition_order(
        session, order, OrderStatus.assigned, ActorType.dispatcher, actor_id
    )


async def get_order(session: AsyncSession, order_id: int) -> Order:
    order = await session.get(Order, order_id)
    if order is None:
        raise NotFoundError("Заказ не найден")
    return order


async def list_orders(
    session: AsyncSession,
    delivery_date=None,
    district_id: int | None = None,
    part: str | None = None,
    status: OrderStatus | None = None,
    driver_id: int | None = None,
    client_id: int | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[Order], int]:
    from sqlalchemy import func as sa_func

    q = select(Order)
    if delivery_date is not None:
        q = q.where(Order.delivery_date == delivery_date)
    if district_id is not None:
        q = q.where(Order.district_id == district_id)
    if part is not None:
        q = q.where(Order.time_window_type == part)
    if status is not None:
        q = q.where(Order.status == status)
    if driver_id is not None:
        q = q.where(Order.assigned_driver_id == driver_id)
    if client_id is not None:
        q = q.where(Order.client_id == client_id)
    total = (await session.execute(q.with_only_columns(sa_func.count(Order.id)))).scalar_one()
    rows = (
        (await session.execute(q.order_by(Order.id.desc()).limit(limit).offset(offset)))
        .scalars()
        .all()
    )
    return list(rows), total

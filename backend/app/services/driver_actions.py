"""Действия водителя (из Telegram-бота). Та же машина состояний, те же order_events."""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ActorType, BatchStatus, OrderStatus, PaymentMethod, WorkStatus
from app.core.phones import normalize_phone as _normalize_phone
from app.models import Driver, Order, RouteBatch
from app.services.errors import NotFoundError, ValidationError
from app.services.orders import transition_order
from app.services.payments import register_payment


async def driver_by_telegram(session: AsyncSession, telegram_id: int) -> Driver | None:
    return (
        await session.execute(select(Driver).where(Driver.telegram_id == telegram_id))
    ).scalar_one_or_none()


async def register_driver_telegram(
    session: AsyncSession, phone: str, telegram_id: int
) -> Driver | None:
    """Привязка telegram_id по номеру телефона (кнопка request_contact).

    None — водитель не найден, бот отвечает «обратитесь к диспетчеру».
    """
    norm = _normalize_phone(phone)
    drivers = (
        (await session.execute(select(Driver).where(Driver.is_active.is_(True)))).scalars().all()
    )
    for d in drivers:
        if _normalize_phone(d.phone) == norm:
            d.telegram_id = telegram_id
            await session.flush()
            return d
    return None


async def _batch_orders(session: AsyncSession, batch_id: int) -> list[Order]:
    return list(
        (
            await session.execute(
                select(Order).where(Order.route_batch_id == batch_id).order_by(Order.route_position)
            )
        )
        .scalars()
        .all()
    )


async def batch_accept(session: AsyncSession, batch: RouteBatch, driver: Driver) -> None:
    """«Принял»: пакет sent -> accepted, заказы -> accepted_by_driver."""
    if batch.status != BatchStatus.sent:
        raise ValidationError(f"Пакет в статусе {batch.status.value}, принять нельзя")
    for o in await _batch_orders(session, batch.id):
        if o.status == OrderStatus.sent_to_driver:
            await transition_order(
                session, o, OrderStatus.accepted_by_driver, ActorType.driver, driver.id
            )
    batch.status = BatchStatus.accepted
    await session.flush()


async def batch_start(session: AsyncSession, batch: RouteBatch, driver: Driver) -> None:
    """«Начал маршрут»: пакет -> started, заказы -> in_progress, водитель on_route."""
    if batch.status != BatchStatus.accepted:
        raise ValidationError(f"Пакет в статусе {batch.status.value}, начать нельзя")
    for o in await _batch_orders(session, batch.id):
        if o.status == OrderStatus.accepted_by_driver:
            await transition_order(session, o, OrderStatus.in_progress, ActorType.driver, driver.id)
    batch.status = BatchStatus.started
    driver.work_status = WorkStatus.on_route
    await session.flush()


async def batch_finish(session: AsyncSession, batch: RouteBatch, driver: Driver) -> None:
    """«Завершил маршрут»: пакет -> finished, водитель idle. Статусы заказов не трогаем —
    незакрытые останутся видны диспетчеру как проблемные."""
    if batch.status != BatchStatus.started:
        raise ValidationError(f"Пакет в статусе {batch.status.value}, завершить нельзя")
    batch.status = BatchStatus.finished
    driver.work_status = WorkStatus.idle
    await session.flush()


async def driver_order(session: AsyncSession, driver: Driver, order_id: int) -> Order:
    order = await session.get(Order, order_id)
    if order is None or order.assigned_driver_id != driver.id:
        raise NotFoundError("Заказ не найден или назначен другому водителю")
    return order


async def order_complete(
    session: AsyncSession,
    driver: Driver,
    order: Order,
    payment_method: PaymentMethod | None,
    amount: Decimal | None,
) -> Order:
    """«Выполнен» + шаг оплаты. payment_method=None — «Без оплаты»."""
    await transition_order(session, order, OrderStatus.completed, ActorType.driver, driver.id)
    if payment_method is not None:
        await register_payment(
            session,
            order,
            payment_method,
            amount if amount is not None else order.total_amount,
            ActorType.driver,
            driver.id,
        )
    return order


async def order_fail(
    session: AsyncSession, driver: Driver, order: Order, reason: str
) -> Order:
    return await transition_order(
        session, order, OrderStatus.failed, ActorType.driver, driver.id, comment=reason
    )


async def order_refuse(
    session: AsyncSession, driver: Driver, order: Order, reason: str
) -> Order:
    return await transition_order(
        session, order, OrderStatus.refused, ActorType.driver, driver.id, comment=reason
    )


async def order_postpone(session: AsyncSession, driver: Driver, order: Order) -> Order:
    """«Перенос»: заказ в postponed, новую дату ставит диспетчер."""
    return await transition_order(
        session, order, OrderStatus.postponed, ActorType.driver, driver.id
    )

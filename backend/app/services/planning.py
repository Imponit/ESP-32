"""Формирование маршрутных пакетов (SPEC.md, разделы 8 и 12)."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.adapters.route_optimizer import RoutePoint, SimpleRouteOptimizer
from app.core.enums import BatchStatus, DayPart, OrderStatus
from app.core.routes import route_link
from app.models import Driver, Order, RouteBatch
from app.services.app_settings import get_max_route_points
from app.services.errors import NotFoundError, ValidationError

_optimizer = SimpleRouteOptimizer()  # MVP-3: OrTools/Yandex через ту же сигнатуру


def build_route_url(orders: list[Order]) -> str | None:
    """Ссылка на маршрут пакета: точки с координатами в порядке диспетчера."""
    points = [
        RoutePoint(o.id, o.address.latitude, o.address.longitude)
        for o in orders
        if o.address.latitude is not None and o.address.longitude is not None
    ]
    points = _optimizer.optimize(points)
    return route_link([(p.latitude, p.longitude) for p in points])


async def create_batch(
    session: AsyncSession,
    delivery_date: date,
    day_part: DayPart,
    district_id: int | None,
    driver_id: int,
    order_ids: list[int],
) -> tuple[RouteBatch, list[str]]:
    """Создать пакет. Возвращает (пакет, предупреждения).

    Жёсткие проверки: лимит точек, заказы в assigned у этого водителя, та же дата.
    Превышение вместимости водителя — предупреждение, не блокировка.
    """
    if not order_ids:
        raise ValidationError("Пустой список заказов")
    max_points = await get_max_route_points(session)
    if len(order_ids) > max_points:
        raise ValidationError(
            f"В пакете не больше {max_points} адресов (передано {len(order_ids)})"
        )

    driver = await session.get(Driver, driver_id)
    if driver is None or not driver.is_active:
        raise NotFoundError("Водитель не найден или деактивирован")

    orders = (
        (
            await session.execute(
                select(Order)
                .where(Order.id.in_(order_ids))
                .options(selectinload(Order.address))  # для route_url нужны координаты
            )
        )
        .scalars()
        .all()
    )
    found = {o.id for o in orders}
    missing = [i for i in order_ids if i not in found]
    if missing:
        raise NotFoundError(f"Заказы не найдены: {missing}")
    for o in orders:
        if o.status != OrderStatus.assigned:
            raise ValidationError(f"Заказ {o.id} не в статусе assigned ({o.status.value})")
        if o.assigned_driver_id != driver_id:
            raise ValidationError(f"Заказ {o.id} назначен другому водителю")
        if o.delivery_date != delivery_date:
            raise ValidationError(f"Заказ {o.id} на другую дату ({o.delivery_date})")
        if o.route_batch_id is not None:
            raise ValidationError(f"Заказ {o.id} уже в пакете {o.route_batch_id}")

    warnings = []
    total_bottles = sum(o.bottles_pc_qty + o.bottles_pet_qty for o in orders)
    if driver.capacity_bottles and total_bottles > driver.capacity_bottles:
        warnings.append(
            f"Бутылей в пакете {total_bottles} — больше вместимости водителя "
            f"({driver.capacity_bottles}). Пакет создан."
        )

    batch = RouteBatch(
        delivery_date=delivery_date,
        day_part=day_part,
        district_id=district_id,
        driver_id=driver_id,
        status=BatchStatus.draft,
    )
    session.add(batch)
    await session.flush()

    by_id = {o.id: o for o in orders}
    ordered = [by_id[i] for i in order_ids]  # порядок диспетчера = route_position
    for pos, o in enumerate(ordered, start=1):
        o.route_batch_id = batch.id
        o.route_position = pos
    batch.route_url = build_route_url(ordered)
    await session.flush()
    return batch, warnings


async def get_batch(session: AsyncSession, batch_id: int) -> RouteBatch:
    batch = await session.get(RouteBatch, batch_id)
    if batch is None:
        raise NotFoundError("Пакет не найден")
    return batch


async def list_batches(session: AsyncSession, delivery_date: date | None) -> list[RouteBatch]:
    q = select(RouteBatch).order_by(RouteBatch.id.desc())
    if delivery_date is not None:
        q = q.where(RouteBatch.delivery_date == delivery_date)
    return list((await session.execute(q)).scalars().all())

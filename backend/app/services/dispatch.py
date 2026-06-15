"""Отправка пакета водителю в Telegram и текст сообщения (SPEC.md, раздел 10)."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.adapters.telegram import TelegramClient
from app.core.enums import ActorType, BatchStatus, OrderStatus
from app.core.routes import point_link
from app.models import Order, RouteBatch
from app.services.errors import ValidationError
from app.services.orders import transition_order

DAY_PART_RU = {"any": "любое время", "first_half": "первая половина дня",
               "second_half": "вторая половина дня"}
PAY_RU = {"cash": "наличные", "cashless": "карта/перевод", "unknown": "уточнить"}


def build_batch_message(batch: RouteBatch, orders: list[Order]) -> str:
    """Сообщение водителю: дата, часть дня, район, маршрут, список заказов."""
    lines = [
        f"📦 Пакет №{batch.id} на {batch.delivery_date.strftime('%d.%m.%Y')}",
        f"Часть дня: {DAY_PART_RU.get(batch.day_part.value, batch.day_part.value)}",
    ]
    if batch.district is not None:
        lines.append(f"Район: {batch.district.name}")
    if batch.route_url:
        lines.append(f"🗺 Маршрут: {batch.route_url}")
    lines.append("")
    for o in orders:
        bottles = []
        if o.bottles_pc_qty:
            bottles.append(f"{o.bottles_pc_qty} поликарбонат")
        if o.bottles_pet_qty:
            bottles.append(f"{o.bottles_pet_qty} ПЭТ")
        if o.pumps_qty:
            bottles.append(f"помпа ×{o.pumps_qty}")
        url = point_link(o.address.latitude, o.address.longitude, o.address_text)
        lines.append(f"{o.route_position}. Заказ №{o.id} — {o.address_text}")
        extra = []
        if o.entrance:
            extra.append(f"подъезд {o.entrance}")
        if o.floor:
            extra.append(f"этаж {o.floor}")
        if extra:
            lines.append("   " + ", ".join(extra))
        lines.append(f"   {o.client_name}, {', '.join(bottles) or 'без бутылей'}")
        lines.append(
            f"   Сумма: {o.total_amount} ₽ ({PAY_RU.get(o.payment_method_plan.value, '?')})"
        )
        if o.comment:
            lines.append(f"   💬 {o.comment}")
        if url:
            lines.append(f"   📍 {url}")
        lines.append("")
    lines.append("Кнопки: «Принял», «Начал маршрут», «Завершил маршрут»")
    return "\n".join(lines)


async def send_batch(
    session: AsyncSession, batch: RouteBatch, telegram: TelegramClient
) -> RouteBatch:
    """Перевести пакет в sent, заказы — в sent_to_driver, отправить сообщение.

    В dry-run сообщение пишется в лог (DryRunTelegramClient).
    """
    if batch.status != BatchStatus.draft:
        raise ValidationError(f"Пакет уже отправлен (статус {batch.status.value})")

    orders = list(
        (
            await session.execute(
                select(Order)
                .where(Order.route_batch_id == batch.id)
                .order_by(Order.route_position)
                .options(selectinload(Order.address))
            )
        )
        .scalars()
        .all()
    )
    if not orders:
        raise ValidationError("В пакете нет заказов")

    for o in orders:
        await transition_order(session, o, OrderStatus.sent_to_driver, ActorType.system)

    batch.status = BatchStatus.sent
    batch.sent_at = datetime.now(UTC)
    await session.flush()

    driver = batch.driver
    text = build_batch_message(batch, orders)
    # Отправка после фиксации статусов; при недоступном Telegram данные уже в базе
    await telegram.send_message(driver.telegram_id, text)
    return batch

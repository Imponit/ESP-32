"""Фиксация оплат (SPEC.md, раздел 13)."""

from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ActorType, PaymentMethod
from app.core.payments import compute_payment_status
from app.models import Order, OrderEvent, Payment
from app.services.errors import ValidationError


async def register_payment(
    session: AsyncSession,
    order: Order,
    method: PaymentMethod,
    amount: Decimal,
    actor_type: ActorType,
    actor_id: int | None = None,
) -> Payment:
    """Создаёт запись в payments, обновляет paid_amount/payment_status, пишет событие."""
    if amount <= 0:
        raise ValidationError("Сумма оплаты должна быть больше нуля")
    payment = Payment(
        order_id=order.id,
        driver_id=order.assigned_driver_id,
        method=method,
        amount=amount,
    )
    session.add(payment)
    order.paid_amount = (order.paid_amount or Decimal("0.00")) + amount
    order.payment_status = compute_payment_status(order.total_amount, order.paid_amount)
    session.add(
        OrderEvent(
            order_id=order.id,
            event_type="payment",
            actor_type=actor_type,
            actor_id=actor_id,
            comment=f"{method.value}: {amount} ₽",
        )
    )
    await session.flush()
    return payment

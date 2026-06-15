"""Чистая логика оплат."""

from decimal import Decimal

from app.core.enums import PaymentStatus


def compute_payment_status(total_amount: Decimal, paid_amount: Decimal) -> PaymentStatus:
    """paid: оплачено всё (или больше); partial: часть; unpaid: ничего."""
    if paid_amount <= 0:
        return PaymentStatus.unpaid
    if paid_amount >= total_amount:
        return PaymentStatus.paid
    return PaymentStatus.partial

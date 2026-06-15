"""Отметка «водитель сдал кассу» за дату (SPEC.md, раздел 13, MVP-2)."""

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CashHandover, Driver
from app.services.errors import NotFoundError


async def mark_cash_handover(
    session: AsyncSession,
    driver_id: int,
    handover_date: date,
    amount: Decimal | None,
    comment: str | None,
    user_id: int | None,
) -> CashHandover:
    """Пометить кассу сданной (upsert по водителю и дате)."""
    driver = await session.get(Driver, driver_id)
    if driver is None:
        raise NotFoundError("Водитель не найден")
    row = (
        await session.execute(
            select(CashHandover).where(
                CashHandover.driver_id == driver_id,
                CashHandover.handover_date == handover_date,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        row = CashHandover(
            driver_id=driver_id,
            handover_date=handover_date,
            amount=amount,
            comment=comment,
            created_by=user_id,
        )
        session.add(row)
    else:
        row.amount = amount
        row.comment = comment
        row.created_by = user_id
    await session.flush()
    return row


async def remove_cash_handover(
    session: AsyncSession, driver_id: int, handover_date: date
) -> bool:
    """Снять отметку. Возвращает True, если запись была."""
    row = (
        await session.execute(
            select(CashHandover).where(
                CashHandover.driver_id == driver_id,
                CashHandover.handover_date == handover_date,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        return False
    await session.delete(row)
    await session.flush()
    return True


async def handovers_for_date(session: AsyncSession, handover_date: date) -> dict[int, CashHandover]:
    rows = (
        await session.execute(
            select(CashHandover).where(CashHandover.handover_date == handover_date)
        )
    ).scalars()
    return {r.driver_id: r for r in rows}

"""Баллы водителей — TODO MVP-2 (SPEC.md, раздел 14).

Правила (коэффициенты) хранятся в settings (JSON), расчёт — по order_events/orders.
Интерфейс закладывается сейчас, реализация — в MVP-2.
"""

from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession


async def compute_driver_scores(session: AsyncSession, period_from: date, period_to: date) -> dict:
    """TODO MVP-2: +1 за completed, бонус за день без failed, −2 за failed без
    причины, −1 за просрочку exact-окна, 0 за refused не по вине водителя."""
    raise NotImplementedError("Баллы водителей — MVP-2")

"""Расчёт баллов водителей (SPEC.md, раздел 14). Чистая логика, без БД.

Коэффициенты приходят из настроек (settings JSON), не зашиты в код. Правила:
- completed: +completed;
- день без failed (есть хотя бы один completed и ноль failed): +day_no_failed_bonus;
- failed без причины (пустой комментарий перехода): +failed_no_reason (обычно −2);
- просрочка exact-окна (completed_at позже time_window_to): +late_exact (обычно −1);
- refused не по вине водителя: +refused_not_driver_fault (обычно 0).
"""

from datetime import datetime
from decimal import Decimal
from typing import Any

from app.core.enums import OrderStatus, TimeWindowType

DEFAULT_SCORING_RULES: dict[str, float] = {
    "completed": 1,
    "day_no_failed_bonus": 2,
    "failed_no_reason": -2,
    "late_exact": -1,
    "refused_not_driver_fault": 0,
}


def _as_aware(dt: datetime, tz) -> datetime:
    """completed_at хранится в UTC; если пришёл наивным (SQLite) — считаем его UTC."""
    if dt.tzinfo is None:
        from datetime import UTC

        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(tz)


def is_late(order: Any, tz) -> bool:
    """Просрочка только для exact-окна: completed_at позже time_window_to в этот день."""
    if order.time_window_type != TimeWindowType.exact:
        return False
    if order.completed_at is None or order.time_window_to is None:
        return False
    local = _as_aware(order.completed_at, tz)
    deadline = datetime.combine(order.delivery_date, order.time_window_to, tzinfo=tz)
    return local > deadline


def compute_scores(
    orders: list[Any],
    failed_has_reason: dict[int, bool],
    driver_names: dict[int, str],
    rules: dict[str, float],
    tz,
) -> list[dict]:
    """Возвращает баллы по каждому водителю с разбивкой. orders — с assigned_driver_id."""
    by_driver: dict[int, list[Any]] = {}
    for o in orders:
        if o.assigned_driver_id is not None:
            by_driver.setdefault(o.assigned_driver_id, []).append(o)

    result = []
    for driver_id, items in by_driver.items():
        completed = [o for o in items if o.status == OrderStatus.completed]
        failed = [o for o in items if o.status == OrderStatus.failed]
        refused = [o for o in items if o.status == OrderStatus.refused]
        late = [o for o in completed if is_late(o, tz)]
        failed_no_reason = [o for o in failed if not failed_has_reason.get(o.id, False)]

        # Бонус за день без failed: есть completed и ноль failed в этот день доставки
        days: dict[Any, dict[str, int]] = {}
        for o in items:
            d = days.setdefault(o.delivery_date, {"completed": 0, "failed": 0})
            if o.status == OrderStatus.completed:
                d["completed"] += 1
            elif o.status == OrderStatus.failed:
                d["failed"] += 1
        bonus_days = [d for d, s in days.items() if s["completed"] >= 1 and s["failed"] == 0]

        completed_points = len(completed) * rules["completed"]
        late_points = len(late) * rules["late_exact"]
        failed_points = len(failed_no_reason) * rules["failed_no_reason"]
        refused_points = len(refused) * rules["refused_not_driver_fault"]
        bonus_points = len(bonus_days) * rules["day_no_failed_bonus"]
        total = (
            completed_points + late_points + failed_points + refused_points + bonus_points
        )

        result.append(
            {
                "driver_id": driver_id,
                "driver_name": driver_names.get(driver_id, "?"),
                "points": _num(total),
                "breakdown": {
                    "completed": len(completed),
                    "completed_points": _num(completed_points),
                    "late_exact": len(late),
                    "late_points": _num(late_points),
                    "failed_no_reason": len(failed_no_reason),
                    "failed_points": _num(failed_points),
                    "refused": len(refused),
                    "refused_points": _num(refused_points),
                    "bonus_days": len(bonus_days),
                    "bonus_points": _num(bonus_points),
                },
            }
        )
    result.sort(key=lambda r: (-r["points"], r["driver_id"]))
    return result


def _num(x: float) -> float | int:
    """Целые баллы отдаём int, дробные — float (коэффициенты могут быть дробными)."""
    f = float(x)
    return int(f) if f == int(f) else round(f, 2)


def merge_rules(custom: dict | None) -> dict[str, float]:
    rules = dict(DEFAULT_SCORING_RULES)
    if custom:
        for k in rules:
            if k in custom:
                rules[k] = float(custom[k])
    return rules


def to_decimal(points: float | int) -> Decimal:
    return Decimal(str(points))

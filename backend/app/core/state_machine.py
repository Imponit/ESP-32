"""Машина состояний заказа (SPEC.md, раздел 6).

Единственная точка правды о разрешённых переходах. Любая смена статуса
(API, бот, система) обязана идти через сервис, который вызывает can_transition.
"""

from app.core.enums import OrderStatus

# Терминальные статусы — из них переходов нет
TERMINAL_STATUSES = frozenset(
    {OrderStatus.completed, OrderStatus.failed, OrderStatus.refused, OrderStatus.cancelled}
)

# cancelled разрешён «из любого статуса до completed» (см. ASSUMPTIONS.md, п. 2)
_CANCELLABLE = frozenset(
    {
        OrderStatus.draft,
        OrderStatus.new,
        OrderStatus.needs_review,
        OrderStatus.planned,
        OrderStatus.assigned,
        OrderStatus.sent_to_driver,
        OrderStatus.accepted_by_driver,
        OrderStatus.in_progress,
        OrderStatus.postponed,
    }
)

ALLOWED_TRANSITIONS: dict[OrderStatus, frozenset[OrderStatus]] = {
    OrderStatus.draft: frozenset({OrderStatus.new}),
    OrderStatus.new: frozenset({OrderStatus.needs_review, OrderStatus.planned}),
    OrderStatus.needs_review: frozenset({OrderStatus.new, OrderStatus.planned}),
    OrderStatus.planned: frozenset({OrderStatus.assigned}),
    OrderStatus.assigned: frozenset({OrderStatus.sent_to_driver, OrderStatus.planned}),
    OrderStatus.sent_to_driver: frozenset({OrderStatus.accepted_by_driver}),
    OrderStatus.accepted_by_driver: frozenset({OrderStatus.in_progress}),
    OrderStatus.in_progress: frozenset(
        {OrderStatus.completed, OrderStatus.failed, OrderStatus.refused, OrderStatus.postponed}
    ),
    OrderStatus.postponed: frozenset({OrderStatus.new}),
}

# Переходы, требующие комментарий/причину
REQUIRES_COMMENT = frozenset({OrderStatus.failed, OrderStatus.refused})


def can_transition(old: OrderStatus, new: OrderStatus) -> bool:
    """Разрешён ли переход old -> new."""
    if new == OrderStatus.cancelled:
        return old in _CANCELLABLE
    return new in ALLOWED_TRANSITIONS.get(old, frozenset())


class TransitionError(Exception):
    """Запрещённый переход или нарушение требований перехода."""


def validate_transition(old: OrderStatus, new: OrderStatus, comment: str | None = None) -> None:
    """Проверка перехода с доменными требованиями. Бросает TransitionError."""
    if not can_transition(old, new):
        raise TransitionError(f"Переход {old.value} → {new.value} запрещён")
    if new in REQUIRES_COMMENT and not (comment and comment.strip()):
        raise TransitionError(f"Переход в {new.value} требует комментарий/причину")

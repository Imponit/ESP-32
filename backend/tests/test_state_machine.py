"""Машина состояний: разрешённые и запрещённые переходы (SPEC.md, раздел 6)."""

import pytest

from app.core.enums import OrderStatus as S
from app.core.state_machine import TransitionError, can_transition, validate_transition

ALLOWED = [
    (S.draft, S.new),
    (S.new, S.needs_review),
    (S.new, S.planned),
    (S.needs_review, S.new),
    (S.needs_review, S.planned),
    (S.planned, S.assigned),
    (S.assigned, S.sent_to_driver),
    (S.assigned, S.planned),  # снять назначение
    (S.sent_to_driver, S.accepted_by_driver),
    (S.accepted_by_driver, S.in_progress),
    (S.in_progress, S.completed),
    (S.in_progress, S.failed),
    (S.in_progress, S.refused),
    (S.in_progress, S.postponed),
    (S.postponed, S.new),
]

FORBIDDEN = [
    (S.new, S.assigned),  # мимо planned
    (S.new, S.completed),
    (S.draft, S.planned),
    (S.planned, S.sent_to_driver),  # мимо assigned
    (S.planned, S.new),
    (S.sent_to_driver, S.in_progress),  # мимо accepted_by_driver
    (S.sent_to_driver, S.planned),
    (S.accepted_by_driver, S.completed),
    (S.completed, S.in_progress),  # из терминального
    (S.completed, S.new),
    (S.cancelled, S.new),
    (S.failed, S.in_progress),
    (S.refused, S.new),
    (S.postponed, S.planned),
    (S.completed, S.completed),
]


@pytest.mark.parametrize(("old", "new"), ALLOWED)
def test_allowed_transitions(old, new):
    assert can_transition(old, new)


@pytest.mark.parametrize(("old", "new"), FORBIDDEN)
def test_forbidden_transitions(old, new):
    assert not can_transition(old, new)


@pytest.mark.parametrize(
    "old",
    [
        S.draft,
        S.new,
        S.needs_review,
        S.planned,
        S.assigned,
        S.sent_to_driver,
        S.accepted_by_driver,
        S.in_progress,
        S.postponed,
    ],
)
def test_cancel_allowed_before_completed(old):
    assert can_transition(old, S.cancelled)


@pytest.mark.parametrize("old", [S.completed, S.failed, S.refused, S.cancelled])
def test_cancel_forbidden_from_terminal(old):
    assert not can_transition(old, S.cancelled)


def test_failed_requires_comment():
    with pytest.raises(TransitionError, match="комментарий"):
        validate_transition(S.in_progress, S.failed, comment=None)
    with pytest.raises(TransitionError):
        validate_transition(S.in_progress, S.refused, comment="   ")
    validate_transition(S.in_progress, S.failed, comment="нет доступа в подъезд")


def test_validate_raises_on_forbidden():
    with pytest.raises(TransitionError, match="запрещён"):
        validate_transition(S.new, S.completed)

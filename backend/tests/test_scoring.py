"""Баллы водителей (MVP-2, раздел 14): completed +1, бонус за день без failed,
failed без причины −2, просрочка exact −1, refused 0, коэффициенты из настроек."""

from datetime import UTC, date, datetime, time
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.core.enums import ActorType, OrderStatus, PaymentMethod, TimeWindowType
from app.core.scoring import compute_scores, merge_rules
from app.models import DriverScore
from app.services import driver_actions
from app.services import orders as orders_service
from app.services.app_settings import set_setting
from app.services.scoring import compute_driver_scores, save_driver_scores
from tests.conftest import order_payload

TZ = ZoneInfo("Europe/Moscow")


class FakeOrder:
    def __init__(self, id, driver_id, status, d, tw=TimeWindowType.any, tw_to=None, completed=None):
        self.id = id
        self.assigned_driver_id = driver_id
        self.status = status
        self.delivery_date = d
        self.time_window_type = tw
        self.time_window_to = tw_to
        self.completed_at = completed


def test_pure_completed_and_day_bonus():
    d = date(2026, 6, 20)
    orders = [
        FakeOrder(1, 7, OrderStatus.completed, d),
        FakeOrder(2, 7, OrderStatus.completed, d),
    ]
    rules = merge_rules(None)
    res = compute_scores(orders, {}, {7: "Сергей"}, rules, TZ)
    assert len(res) == 1
    r = res[0]
    # 2 completed (+2) + бонус за день без failed (+2) = 4
    assert r["points"] == 4
    assert r["breakdown"]["completed"] == 2
    assert r["breakdown"]["bonus_days"] == 1


def test_pure_failed_no_reason_penalty_and_no_bonus():
    d = date(2026, 6, 20)
    orders = [
        FakeOrder(1, 7, OrderStatus.completed, d),
        FakeOrder(2, 7, OrderStatus.failed, d),
    ]
    rules = merge_rules(None)
    # failed без причины
    res = compute_scores(orders, {2: False}, {7: "С"}, rules, TZ)
    r = res[0]
    # completed +1, failed без причины −2, бонуса за день нет (есть failed) => -1
    assert r["points"] == -1
    assert r["breakdown"]["failed_no_reason"] == 1
    assert r["breakdown"]["bonus_days"] == 0


def test_pure_failed_with_reason_not_penalized():
    d = date(2026, 6, 20)
    orders = [FakeOrder(1, 7, OrderStatus.failed, d)]
    res = compute_scores(orders, {1: True}, {7: "С"}, merge_rules(None), TZ)
    assert res[0]["breakdown"]["failed_no_reason"] == 0
    assert res[0]["points"] == 0


def test_pure_late_exact_penalty():
    d = date(2026, 6, 20)
    # окно до 12:00 МСК, выполнено в 13:00 МСК (= 10:00 UTC)
    late_completed = datetime(2026, 6, 20, 10, 0, tzinfo=UTC)
    orders = [
        FakeOrder(1, 7, OrderStatus.completed, d, TimeWindowType.exact, time(12, 0), late_completed)
    ]
    res = compute_scores(orders, {}, {7: "С"}, merge_rules(None), TZ)
    # completed +1, просрочка −1, бонус за день +2 = 2
    assert res[0]["breakdown"]["late_exact"] == 1
    assert res[0]["points"] == 2


def test_pure_on_time_exact_no_penalty():
    d = date(2026, 6, 20)
    on_time = datetime(2026, 6, 20, 8, 0, tzinfo=UTC)  # 11:00 МСК < 12:00
    orders = [
        FakeOrder(1, 7, OrderStatus.completed, d, TimeWindowType.exact, time(12, 0), on_time)
    ]
    res = compute_scores(orders, {}, {7: "С"}, merge_rules(None), TZ)
    assert res[0]["breakdown"]["late_exact"] == 0


def test_custom_rules_from_settings_override():
    d = date(2026, 6, 20)
    orders = [FakeOrder(1, 7, OrderStatus.completed, d)]
    rules = merge_rules({"completed": 5, "day_no_failed_bonus": 0})
    res = compute_scores(orders, {}, {7: "С"}, rules, TZ)
    assert res[0]["points"] == 5  # 1*5 + bonus 0


# --- Интеграция с БД ---


async def _complete_order(session, fx, with_reason_fail=False):
    order = await orders_service.create_order(session, order_payload(fx), actor_id=1)
    await orders_service.assign_driver(session, order, fx["driver"].id, actor_id=1)
    await orders_service.transition_order(
        session, order, OrderStatus.sent_to_driver, ActorType.dispatcher, 1
    )
    await orders_service.transition_order(
        session, order, OrderStatus.accepted_by_driver, ActorType.driver, fx["driver"].id
    )
    await orders_service.transition_order(
        session, order, OrderStatus.in_progress, ActorType.driver, fx["driver"].id
    )
    return order


async def test_db_scoring_end_to_end(session, fixtures):
    driver = fixtures["driver"]
    order = await _complete_order(session, fixtures)
    await driver_actions.order_complete(session, driver, order, PaymentMethod.cash, None)

    scores = await compute_driver_scores(session, date.today(), date.today())
    assert len(scores) == 1
    s = scores[0]
    assert s["driver_id"] == driver.id
    assert s["breakdown"]["completed"] == 1
    assert s["points"] == 3  # completed +1, бонус за день +2


async def test_db_failed_with_reason_no_penalty(session, fixtures):
    driver = fixtures["driver"]
    order = await _complete_order(session, fixtures)
    await driver_actions.order_fail(session, driver, order, "нет доступа в подъезд")

    scores = await compute_driver_scores(session, date.today(), date.today())
    s = scores[0]
    assert s["breakdown"]["failed_no_reason"] == 0  # причина указана
    assert s["points"] == 0


async def test_db_rules_from_settings(session, fixtures):
    await set_setting(session, "scoring_rules", {"completed": 10, "day_no_failed_bonus": 0})
    driver = fixtures["driver"]
    order = await _complete_order(session, fixtures)
    await driver_actions.order_complete(session, driver, order, PaymentMethod.cash, None)

    scores = await compute_driver_scores(session, date.today(), date.today())
    assert scores[0]["points"] == 10


async def test_save_driver_scores_persists(session, fixtures):
    driver = fixtures["driver"]
    order = await _complete_order(session, fixtures)
    await driver_actions.order_complete(session, driver, order, PaymentMethod.cash, None)

    rows = await save_driver_scores(session, date.today(), date.today())
    assert len(rows) == 1
    saved = (await session.execute(select(DriverScore))).scalar_one()
    assert saved.driver_id == driver.id
    assert saved.points == Decimal("3")

"""Журнал событий (MVP-2): лента order_events с фильтрами и обогащением."""

from datetime import date

from app.core.enums import ActorType, OrderStatus, PaymentMethod
from app.services import driver_actions
from app.services import orders as orders_service
from app.services.events import list_events
from tests.conftest import order_payload


async def _order_with_history(session, fx):
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
    await driver_actions.order_complete(session, fx["driver"], order, PaymentMethod.cash, None)
    return order


async def test_list_events_enriched(session, fixtures):
    order = await _order_with_history(session, fixtures)
    items, total = await list_events(session)

    assert total >= 6  # created, planned, assigned, sent, accepted, in_progress, completed, payment
    assert items[0]["id"] > items[-1]["id"]  # сортировка: новые сверху
    # обогащение контекстом заказа
    assert all(e["order_id"] == order.id for e in items)
    assert items[0]["order_client_name"] == "Иван Петров"
    assert items[0]["order_address"]


async def test_actor_names_resolved(session, fixtures):
    await _order_with_history(session, fixtures)
    items, _ = await list_events(session, actor_type=ActorType.driver)
    assert items, "должны быть события водителя"
    assert all(e["actor_type"] == "driver" for e in items)
    assert all(e["actor_name"] == fixtures["driver"].name for e in items)


async def test_filter_by_event_type_payment(session, fixtures):
    await _order_with_history(session, fixtures)
    items, total = await list_events(session, event_type="payment")
    assert total == 1
    assert items[0]["event_type"] == "payment"
    assert "cash" in (items[0]["comment"] or "")


async def test_filter_by_order_id(session, fixtures):
    await _order_with_history(session, fixtures)
    o2 = await orders_service.create_order(session, order_payload(fixtures), actor_id=1)

    _, total_all = await list_events(session)
    items_o2, total_o2 = await list_events(session, order_id=o2.id)
    assert total_o2 == 1  # только событие created
    assert all(e["order_id"] == o2.id for e in items_o2)
    assert total_all > total_o2


async def test_pagination(session, fixtures):
    await _order_with_history(session, fixtures)
    page1, total = await list_events(session, limit=3, offset=0)
    page2, _ = await list_events(session, limit=3, offset=3)
    assert len(page1) == 3
    assert {e["id"] for e in page1}.isdisjoint({e["id"] for e in page2})


async def test_filter_by_date(session, fixtures):
    await _order_with_history(session, fixtures)
    today = date.today()
    items_today, total_today = await list_events(session, date_from=today, date_to=today)
    assert total_today >= 6
    _, total_past = await list_events(
        session, date_from=date(2000, 1, 1), date_to=date(2000, 1, 2)
    )
    assert total_past == 0


async def test_failed_reason_visible_in_journal(session, fixtures):
    order = await orders_service.create_order(session, order_payload(fixtures), actor_id=1)
    await orders_service.assign_driver(session, order, fixtures["driver"].id, actor_id=1)
    await orders_service.transition_order(
        session, order, OrderStatus.sent_to_driver, ActorType.dispatcher, 1
    )
    await orders_service.transition_order(
        session, order, OrderStatus.accepted_by_driver, ActorType.driver, fixtures["driver"].id
    )
    await orders_service.transition_order(
        session, order, OrderStatus.in_progress, ActorType.driver, fixtures["driver"].id
    )
    await driver_actions.order_fail(session, fixtures["driver"], order, "нет дома")

    items, _ = await list_events(session, event_type="status_change")
    failed = [e for e in items if e["new_status"] == "failed"]
    assert len(failed) == 1
    assert failed[0]["comment"] == "нет дома"

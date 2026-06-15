"""Оптимизация маршрута (MVP-3): haversine, жадный оптимизатор, интеграция с пакетом."""

from datetime import date
from decimal import Decimal

import pytest

from app.adapters.route_optimizer import (
    GreedyRouteOptimizer,
    RoutePoint,
    SimpleRouteOptimizer,
    get_route_optimizer,
)
from app.core.enums import DayPart
from app.core.geo import haversine_km
from app.models import Address, Client, District
from app.services import orders as orders_service
from app.services.app_settings import set_setting
from app.services.planning import create_batch


def test_haversine_known_distance():
    # Москва — Санкт-Петербург ~633 км
    d = haversine_km(55.7558, 37.6173, 59.9343, 30.3351)
    assert 600 < d < 670


def test_haversine_zero():
    assert haversine_km(47.1, 37.5, 47.1, 37.5) == pytest.approx(0.0, abs=1e-6)


def _pt(oid, lat, lon):
    return RoutePoint(oid, Decimal(str(lat)) if lat is not None else None,
                      Decimal(str(lon)) if lon is not None else None)


def test_greedy_orders_by_proximity():
    # точки на линии; диспетчер дал «вперемешку», ожидаем проход по возрастанию
    points = [_pt(1, 0.0, 0.0), _pt(2, 0.0, 3.0), _pt(3, 0.0, 1.0), _pt(4, 0.0, 2.0)]
    result = GreedyRouteOptimizer().optimize(points)
    assert [p.order_id for p in result] == [1, 3, 4, 2]


def test_greedy_keeps_points_without_coords_at_end():
    points = [_pt(1, 0.0, 0.0), _pt(2, None, None), _pt(3, 0.0, 1.0)]
    result = GreedyRouteOptimizer().optimize(points)
    assert result[-1].order_id == 2  # без координат — в конец
    assert {p.order_id for p in result[:2]} == {1, 3}


def test_greedy_small_input_unchanged():
    points = [_pt(1, 0.0, 0.0), _pt(2, 0.0, 9.0)]
    assert [p.order_id for p in GreedyRouteOptimizer().optimize(points)] == [1, 2]


def test_simple_optimizer_identity():
    points = [_pt(3, 0.0, 0.0), _pt(1, 0.0, 1.0)]
    assert [p.order_id for p in SimpleRouteOptimizer().optimize(points)] == [3, 1]


def test_get_route_optimizer_unknown():
    with pytest.raises(ValueError, match="Неизвестный"):
        get_route_optimizer("nope")


def test_ortools_yandex_stubs_raise():
    with pytest.raises(NotImplementedError):
        get_route_optimizer("ortools").optimize([])
    with pytest.raises(NotImplementedError):
        get_route_optimizer("yandex").optimize([])


# --- интеграция с формированием пакета ---


async def _setup(session):
    district = District(name="Центральный", sort_order=1)
    session.add(district)
    await session.flush()
    client = Client(name="Тест", phone_primary="+7 900 000-00-00")
    session.add(client)
    await session.flush()
    driver_district = district
    # водитель
    from app.models import Driver

    driver = Driver(name="Сергей", phone="+7 900 555-66-77", capacity_bottles=99)
    session.add(driver)
    await session.flush()
    return district, client, driver, driver_district


async def _assigned_order(session, client, driver, lat, lon):
    addr = Address(
        client_id=client.id, raw_address=f"точка {lat},{lon}",
        latitude=Decimal(str(lat)), longitude=Decimal(str(lon)),
    )
    session.add(addr)
    await session.flush()
    order = await orders_service.create_order(
        session,
        {"client_id": client.id, "address_id": addr.id, "delivery_date": date.today(),
         "bottles_pc_qty": 1, "total_amount": Decimal("300.00")},
        actor_id=1,
    )
    await orders_service.assign_driver(session, order, driver.id, actor_id=1)
    return order


async def test_batch_optimize_sets_positions_and_url(session):
    _, client, driver, _ = await _setup(session)
    o1 = await _assigned_order(session, client, driver, 0.0, 0.0)
    o2 = await _assigned_order(session, client, driver, 0.0, 3.0)
    o3 = await _assigned_order(session, client, driver, 0.0, 1.0)

    await set_setting(session, "route_optimizer", "greedy")
    batch, _ = await create_batch(
        session, date.today(), DayPart.any, None, driver.id,
        [o1.id, o2.id, o3.id], optimize=True,
    )
    # ожидаемый оптимальный порядок: o1(0)->o3(1)->o2(3)
    positions = {o.id: o.route_position for o in (o1, o2, o3)}
    assert positions == {o1.id: 1, o3.id: 2, o2.id: 3}
    # ссылка строится в том же порядке (координаты округлены до 6 знаков в БД)
    i0 = batch.route_url.index("0.000000,0.000000")
    i1 = batch.route_url.index("0.000000,1.000000")
    i3 = batch.route_url.index("0.000000,3.000000")
    assert i0 < i1 < i3


async def test_batch_without_optimize_keeps_dispatcher_order(session):
    _, client, driver, _ = await _setup(session)
    o1 = await _assigned_order(session, client, driver, 0.0, 0.0)
    o2 = await _assigned_order(session, client, driver, 0.0, 3.0)
    o3 = await _assigned_order(session, client, driver, 0.0, 1.0)

    batch, _ = await create_batch(
        session, date.today(), DayPart.any, None, driver.id,
        [o1.id, o2.id, o3.id], optimize=False,
    )
    assert {o.id: o.route_position for o in (o1, o2, o3)} == {o1.id: 1, o2.id: 2, o3.id: 3}

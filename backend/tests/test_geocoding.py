"""Геокодинг (MVP-2): кэш, неточность -> needs_review, недоступность -> pending,
не найдено -> failed, ручные координаты не перетираются, парсинг ответа Яндекса."""

from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.adapters.geocoder import (
    GeocodeResult,
    GeocoderUnavailableError,
    MockGeocoderProvider,
    YandexGeocoderProvider,
)
from app.core.enums import GeocodeStatus, OrderStatus
from app.models import Address, Client, District, GeocodeCache
from app.services import orders as orders_service
from app.services.app_settings import set_setting
from app.services.geocoding import geocode_address, normalize_address


def _order_data(client_id, address_id):
    return {
        "client_id": client_id,
        "address_id": address_id,
        "delivery_date": date.today(),
        "total_amount": Decimal("300.00"),
    }


_district_seq = 0


async def _client_and_address(session, raw="пр. Мира, 12", with_coords=False):
    global _district_seq
    _district_seq += 1
    district = District(name=f"Центральный-{_district_seq}", sort_order=1)
    session.add(district)
    await session.flush()
    client = Client(name="Тест", phone_primary="+7 900 000-00-00")
    session.add(client)
    await session.flush()
    address = Address(
        client_id=client.id,
        raw_address=raw,
        district_id=district.id,
        latitude=Decimal("47.0") if with_coords else None,
        longitude=Decimal("37.0") if with_coords else None,
        geocode_status=GeocodeStatus.manual if with_coords else GeocodeStatus.none,
    )
    session.add(address)
    await session.flush()
    return client, address


def _result(conf="1.000", precision="exact"):
    return GeocodeResult(
        latitude=Decimal("47.097100"),
        longitude=Decimal("37.543400"),
        normalized_address="Россия, Мариуполь, проспект Мира, 12",
        confidence=Decimal(conf),
        precision=precision,
    )


def test_normalize_address():
    # нижний регистр, схлопнутые пробелы, без хвостовой пунктуации
    assert normalize_address("  ПР.  Мира,  12 . ") == "пр. мира, 12"
    assert normalize_address("ПР. Мира, 12") == normalize_address("пр. мира, 12,")


async def test_geocode_ok_writes_coords_and_cache(session):
    _, address = await _client_and_address(session)
    provider = MockGeocoderProvider({"пр. Мира, 12": _result()})
    res = await geocode_address(session, address, provider)

    assert res["status"] == "ok"
    assert res["from_cache"] is False
    assert address.geocode_status == GeocodeStatus.ok
    assert address.latitude == Decimal("47.097100")
    assert address.geocode_confidence == Decimal("1.000")
    cache = (await session.execute(select(GeocodeCache))).scalars().all()
    assert len(cache) == 1


async def test_geocode_uses_cache_without_calling_provider(session):
    _, a1 = await _client_and_address(session, raw="пр. Мира, 12")
    provider = MockGeocoderProvider({"пр. Мира, 12": _result()})
    await geocode_address(session, a1, provider)

    # Второй адрес с тем же текстом -> берём из кэша, провайдер не вызывается повторно
    _, a2 = await _client_and_address(session, raw="ПР. Мира, 12 ")
    res = await geocode_address(session, a2, provider)
    assert res["status"] == "ok"
    assert res["from_cache"] is True
    assert provider.calls == ["пр. Мира, 12"]  # ровно один вызов на оба адреса


async def test_low_confidence_moves_orders_to_needs_review(session):
    client, address = await _client_and_address(session)
    order = await orders_service.create_order(
        session, _order_data(client.id, address.id), actor_id=1
    )
    assert order.status == OrderStatus.new

    provider = MockGeocoderProvider({"пр. Мира, 12": _result(conf="0.500", precision="street")})
    res = await geocode_address(session, address, provider)

    assert res["status"] == "ok"
    assert res["imprecise"] is True
    assert res["needs_review_order_ids"] == [order.id]
    assert order.status == OrderStatus.needs_review


async def test_precise_result_keeps_orders_new(session):
    client, address = await _client_and_address(session)
    order = await orders_service.create_order(
        session, _order_data(client.id, address.id), actor_id=1
    )
    provider = MockGeocoderProvider({"пр. Мира, 12": _result()})
    res = await geocode_address(session, address, provider)
    assert res["imprecise"] is False
    assert order.status == OrderStatus.new


async def test_provider_unavailable_sets_pending(session):
    _, address = await _client_and_address(session)
    provider = MockGeocoderProvider(fail_for={"пр. Мира, 12"})
    res = await geocode_address(session, address, provider)
    assert res["status"] == "pending"
    assert address.geocode_status == GeocodeStatus.pending
    assert address.latitude is None  # данные не потеряны, координат просто нет


async def test_address_not_found_sets_failed(session):
    _, address = await _client_and_address(session)
    provider = MockGeocoderProvider(results={})  # ничего не найдено
    res = await geocode_address(session, address, provider)
    assert res["status"] == "failed"
    assert address.geocode_status == GeocodeStatus.failed


async def test_manual_coords_not_overwritten(session):
    _, address = await _client_and_address(session, with_coords=True)
    provider = MockGeocoderProvider({"пр. Мира, 12": _result()})
    res = await geocode_address(session, address, provider)
    assert res["status"] == "skipped_manual"
    assert address.latitude == Decimal("47.0")  # ручные координаты сохранены
    assert provider.calls == []


async def test_force_regeocodes_manual(session):
    _, address = await _client_and_address(session, with_coords=True)
    provider = MockGeocoderProvider({"пр. Мира, 12": _result()})
    res = await geocode_address(session, address, provider, force=True)
    assert res["status"] == "ok"
    assert address.latitude == Decimal("47.097100")


async def test_confidence_threshold_from_settings(session):
    # Понизим порог до 0.4 — результат street(0.5) теперь считается точным
    await set_setting(session, "geocode_confidence_threshold", 0.4)
    client, address = await _client_and_address(session)
    order = await orders_service.create_order(
        session, _order_data(client.id, address.id), actor_id=1
    )
    provider = MockGeocoderProvider({"пр. Мира, 12": _result(conf="0.500", precision="street")})
    res = await geocode_address(session, address, provider)
    assert res["imprecise"] is False
    assert order.status == OrderStatus.new


def test_yandex_parse_extracts_point_and_precision():
    payload = {
        "response": {
            "GeoObjectCollection": {
                "featureMember": [
                    {
                        "GeoObject": {
                            "Point": {"pos": "37.543400 47.097100"},
                            "metaDataProperty": {
                                "GeocoderMetaData": {
                                    "precision": "exact",
                                    "text": "Мариуполь, проспект Мира, 12",
                                }
                            },
                        }
                    }
                ]
            }
        }
    }
    result = YandexGeocoderProvider._parse(payload)
    assert result.latitude == Decimal("47.097100")
    assert result.longitude == Decimal("37.543400")
    assert result.precision == "exact"
    assert result.confidence == Decimal("1.000")


def test_yandex_parse_empty_returns_none():
    payload = {"response": {"GeoObjectCollection": {"featureMember": []}}}
    assert YandexGeocoderProvider._parse(payload) is None


def test_yandex_parse_garbage_raises_unavailable():
    try:
        YandexGeocoderProvider._parse({"unexpected": True})
    except GeocoderUnavailableError:
        return
    raise AssertionError("ожидался GeocoderUnavailableError")

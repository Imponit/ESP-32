"""Импорт заказов из CSV/XLSX (MVP-2): парсинг, find-or-create, ошибки строк,
dry-run, район по имени, обязательные колонки, XLSX."""

import io

import pytest
from sqlalchemy import func, select

from app.core.enums import SourceType, TimeWindowType
from app.models import Address, Client, District, Order
from app.services.importing import ImportError_, import_orders

CSV_HEADER = "имя,телефон,адрес,район,дата,часть_дня,бутыли_пк,сумма,оплата,комментарий"


@pytest.fixture
async def district(session):
    d = District(name="Центральный", sort_order=1)
    session.add(d)
    await session.flush()
    return d


def _csv(*lines: str) -> bytes:
    return ("\n".join([CSV_HEADER, *lines])).encode()


async def _count(session, model) -> int:
    return (await session.execute(select(func.count()).select_from(model))).scalar_one()


async def test_import_creates_client_address_order(session, district):
    content = _csv(
        "Иван Петров,+79001112233,Мира 12,Центральный,2026-06-20,первая,2,600,наличные,домофон"
    )
    report = await import_orders(session, "orders.csv", content, actor_id=1)

    assert report.total_rows == 1
    assert report.imported == 1
    assert report.clients_created == 1
    assert report.addresses_created == 1
    assert report.errors == []

    order = (await session.execute(select(Order))).scalar_one()
    assert order.client_name == "Иван Петров"
    assert order.district_id == district.id
    assert order.bottles_pc_qty == 2
    assert order.time_window_type == TimeWindowType.first_half
    assert order.source_type == SourceType.import_
    assert order.comment == "домофон"


async def test_import_reuses_existing_client_by_phone(session, district):
    # два заказа на один и тот же телефон -> один клиент, один адрес
    content = _csv(
        "Иван,+7 900 111-22-33,пр. Мира 12,Центральный,2026-06-20,,1,300,наличные,",
        "Иван П.,8 (900) 111-22-33,пр. Мира 12,Центральный,2026-06-21,,2,600,карта,",
    )
    report = await import_orders(session, "orders.csv", content, actor_id=1)
    assert report.imported == 2
    assert report.clients_created == 1  # второй заказ переиспользовал клиента
    assert report.addresses_created == 1
    assert await _count(session, Client) == 1
    assert await _count(session, Order) == 2


async def test_import_bad_rows_go_to_errors_others_saved(session, district):
    content = _csv(
        "Ок,+7 900 000-00-01,адрес 1,Центральный,2026-06-20,,1,300,наличные,",
        "Плохая дата,+7 900 000-00-02,адрес 2,Центральный,НЕ-ДАТА,,1,300,наличные,",
        "Чужой район,+7 900 000-00-03,адрес 3,Несуществующий,2026-06-20,,1,300,наличные,",
        ",+7 900 000-00-04,адрес 4,Центральный,2026-06-20,,1,300,наличные,",
    )
    report = await import_orders(session, "orders.csv", content, actor_id=1)
    assert report.imported == 1
    assert len(report.errors) == 3
    rows_with_errors = {e["row"] for e in report.errors}
    assert rows_with_errors == {3, 4, 5}  # строка 1 — заголовок
    # только валидная строка сохранилась
    assert await _count(session, Order) == 1


async def test_dry_run_does_not_persist(session, district):
    content = _csv(
        "Иван,+7 900 111-22-33,пр. Мира 12,Центральный,2026-06-20,,2,600,наличные,"
    )
    report = await import_orders(session, "orders.csv", content, actor_id=1, dry_run=True)
    assert report.dry_run is True
    assert report.imported == 1
    assert report.order_ids == []  # в предпросмотре id не возвращаются
    assert await _count(session, Order) == 0  # ничего не сохранилось
    assert await _count(session, Client) == 0


async def test_missing_required_column_raises(session, district):
    bad = "name,address,date\nИван,адрес,2026-06-20".encode()  # нет телефона
    with pytest.raises(ImportError_, match="phone"):
        await import_orders(session, "orders.csv", bad, actor_id=1)


async def test_unsupported_format_raises(session):
    with pytest.raises(ImportError_, match="csv и .xlsx"):
        await import_orders(session, "orders.pdf", b"...", actor_id=1)


async def test_semicolon_delimiter_csv(session, district):
    content = (
        "имя;телефон;адрес;дата;сумма\n"
        "Семён;+7 900 222-33-44;ул. Зелёная 5;20.06.2026;450"
    ).encode()
    report = await import_orders(session, "orders.csv", content, actor_id=1)
    assert report.imported == 1
    order = (await session.execute(select(Order))).scalar_one()
    assert order.total_amount == __import_decimal("450")
    assert str(order.delivery_date) == "2026-06-20"


async def test_import_xlsx(session, district):
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["имя", "телефон", "адрес", "район", "дата", "бутыли_пк", "сумма"])
    ws.append(["Анна", "+7 900 555-66-77", "пр. Ленина 1", "Центральный", "2026-06-20", 3, 900])
    buf = io.BytesIO()
    wb.save(buf)

    report = await import_orders(session, "orders.xlsx", buf.getvalue(), actor_id=1)
    assert report.imported == 1
    order = (await session.execute(select(Order))).scalar_one()
    assert order.client_name == "Анна"
    assert order.bottles_pc_qty == 3


async def test_import_with_manual_coords_sets_address(session, district):
    content = (
        "имя,телефон,адрес,дата,широта,долгота\n"
        "Гео,+7 900 777-88-99,пр. Мира 12,2026-06-20,47.0971,37.5434"
    ).encode()
    report = await import_orders(session, "orders.csv", content, actor_id=1)
    assert report.imported == 1
    address = (await session.execute(select(Address))).scalar_one()
    assert str(address.latitude) == "47.097100"
    assert address.geocode_status.value == "manual"


def __import_decimal(s):
    from decimal import Decimal

    return Decimal(s)

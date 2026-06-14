"""Синхронизация заявок из Google Sheets (MVP-3): маппинг, дедуп, приём."""

from app.adapters.google_sheets import (
    MockGoogleSheetsAdapter,
    _rows_from_csv,
)
from app.core.enums import IncomingStatus, SourceType
from app.services.intake import list_incoming
from app.services.sheets_intake import (
    _build_header_map,
    row_to_fields,
    sync_google_sheet,
)


def test_rows_from_csv():
    text = "имя,телефон\nИван,+7 949 111-22-33\n,\nПётр,+7 949 222-33-44"
    rows = _rows_from_csv(text)
    assert len(rows) == 2  # пустая строка пропущена
    assert rows[0] == {"имя": "Иван", "телефон": "+7 949 111-22-33"}


def test_row_to_fields_maps_columns():
    headers = ["имя", "телефон", "адрес", "район", "дата", "бутыли_пк", "сумма", "комментарий"]
    hmap = _build_header_map(headers)
    row = {
        "имя": "Иван", "телефон": "+7 949 111-22-33", "адрес": "ул. Мира 12",
        "район": "Центральный", "дата": "2026-06-20", "бутыли_пк": "3",
        "сумма": "900", "комментарий": "домофон",
    }
    f = row_to_fields(row, hmap)
    assert f["name"] == "Иван"
    assert f["phone_normalized"] == "9491112233"
    assert f["address"] == "ул. Мира 12"
    assert f["district_name"] == "Центральный"
    assert f["delivery_date"] == "2026-06-20"
    assert f["bottles_pc_qty"] == 3
    assert f["total_amount"] == "900"
    assert f["comment"] == "домофон"


def test_row_to_fields_lenient_on_bad_values():
    hmap = _build_header_map(["имя", "дата", "бутыли_пк"])
    f = row_to_fields({"имя": "А", "дата": "не-дата", "бутыли_пк": "abc"}, hmap)
    assert f["name"] == "А"
    assert "delivery_date" not in f  # плохая дата просто не заполнена
    assert "bottles_pc_qty" not in f


async def test_sync_ingests_new_rows(session):
    rows = [
        {"имя": "Иван", "телефон": "+7 949 111-22-33", "адрес": "ул. Мира 12",
         "дата": "2026-06-20"},
        {"имя": "Пётр", "телефон": "+7 949 222-33-44", "адрес": "ул. Ленина 5",
         "дата": "2026-06-21"},
    ]
    adapter = MockGoogleSheetsAdapter(rows)
    res = await sync_google_sheet(session, adapter)
    assert res == {"total_rows": 2, "ingested": 2, "skipped": 0}

    items, total = await list_incoming(session, source_type=SourceType.google_sheets)
    assert total == 2
    assert all(m.status == IncomingStatus.new for m in items)
    assert all(m.external_id.startswith("gsheet:") for m in items)


async def test_sync_dedupes_already_imported(session):
    rows = [{"имя": "Иван", "телефон": "+7 949 111-22-33", "адрес": "ул. Мира 12"}]
    adapter = MockGoogleSheetsAdapter(rows)
    first = await sync_google_sheet(session, adapter)
    assert first["ingested"] == 1
    # повторная синхронизация той же строки -> пропуск
    second = await sync_google_sheet(session, adapter)
    assert second == {"total_rows": 1, "ingested": 0, "skipped": 1}

    _, total = await list_incoming(session, source_type=SourceType.google_sheets)
    assert total == 1


async def test_sync_new_row_added_later(session):
    a1 = MockGoogleSheetsAdapter([{"имя": "Иван", "телефон": "+7 949 111-22-33"}])
    await sync_google_sheet(session, a1)
    a2 = MockGoogleSheetsAdapter([
        {"имя": "Иван", "телефон": "+7 949 111-22-33"},  # уже есть
        {"имя": "Пётр", "телефон": "+7 949 222-33-44"},  # новая
    ])
    res = await sync_google_sheet(session, a2)
    assert res == {"total_rows": 2, "ingested": 1, "skipped": 1}


async def test_sync_empty_sheet(session):
    res = await sync_google_sheet(session, MockGoogleSheetsAdapter([]))
    assert res == {"total_rows": 0, "ingested": 0, "skipped": 0}

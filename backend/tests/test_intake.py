"""Входящие заявки (MVP-3): парсер текста, приём, конвертация, игнор, вебхук-адаптер."""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.adapters.incoming import (
    IncomingPayload,
    MockIncomingAdapter,
    TelegramIncomingAdapter,
)
from app.core.enums import IncomingStatus, SourceType
from app.core.intake_parser import parse_request_text
from app.models import Client, Order
from app.services.errors import ValidationError
from app.services.intake import (
    convert_to_order,
    ignore_message,
    ingest_payload,
    list_incoming,
)

# --- Парсер ---


def test_parser_extracts_phone_address_bottles_date():
    text = (
        "Здравствуйте, меня зовут Иван. Нужно 3 бутыли на завтра. "
        "ул. Мира, д. 12, кв. 5. +7 949 111-22-33"
    )
    res = parse_request_text(text, today=date(2026, 6, 20))
    f = res["fields"]
    assert f["phone_normalized"] == "9491112233"
    assert f["name"] == "Иван"
    assert "Мира" in f["address"]
    assert "+7" not in f["address"]  # телефон не попал в адрес
    assert f["bottles_pc_qty"] == 3
    assert f["delivery_date"] == "2026-06-21"  # завтра


def test_parser_explicit_date_and_part():
    res = parse_request_text("Привет, 2 бутылки 25.06.2026 после обеда", today=date(2026, 6, 20))
    assert res["fields"]["delivery_date"] == "2026-06-25"
    assert res["fields"]["time_window_type"] == "second_half"
    assert res["fields"]["bottles_pc_qty"] == 2


def test_parser_notes_when_missing():
    res = parse_request_text("Просто текст без данных")
    assert "телефон не распознан" in res["notes"]
    assert "адрес не распознан" in res["notes"]


# --- Адаптеры ---


def test_telegram_adapter_parses_update():
    update = {
        "message": {
            "message_id": 42,
            "date": 1750000000,
            "text": "Нужна вода",
            "chat": {"id": 555},
            "from": {"first_name": "Пётр", "last_name": "С", "username": "petr"},
        }
    }
    payload = TelegramIncomingAdapter().parse_update(update)
    assert payload.source_type == SourceType.telegram
    assert payload.text == "Нужна вода"
    assert payload.external_id == "42"
    assert payload.sender == "555"
    assert payload.sender_name == "Пётр С"


def test_telegram_adapter_ignores_non_text():
    assert TelegramIncomingAdapter().parse_update({"message": {"sticker": {}}}) is None
    assert TelegramIncomingAdapter().parse_update({}) is None


# --- Пайплайн ---


async def test_ingest_stores_and_parses(session):
    payload = IncomingPayload(
        source_type=SourceType.telegram,
        text="3 бутыли, ул. Ленина 5, +7 949 700-00-11",
        sender="555",
        sender_name="Аноним",
    )
    msg = await ingest_payload(session, payload)
    assert msg.status == IncomingStatus.new
    assert msg.parsed["fields"]["bottles_pc_qty"] == 3
    assert msg.parsed["fields"]["phone_normalized"] == "9497000011"


async def test_ingest_uses_sender_phone_when_text_has_none(session):
    payload = IncomingPayload(
        source_type=SourceType.sms, text="Привезите воду завтра", sender="89497000022"
    )
    msg = await ingest_payload(session, payload)
    assert msg.parsed["fields"]["phone_normalized"] == "9497000022"


async def test_list_incoming_filter_by_status(session):
    await ingest_payload(session, IncomingPayload(SourceType.telegram, "2 бутыли ул. А 1"))
    await ingest_payload(session, IncomingPayload(SourceType.telegram, "5 бутылей ул. Б 2"))
    items, total = await list_incoming(session, status=IncomingStatus.new)
    assert total == 2
    assert all(m.status == IncomingStatus.new for m in items)


async def test_convert_creates_order_and_client(session):
    msg = await ingest_payload(
        session,
        IncomingPayload(SourceType.telegram, "3 бутыли ул. Мира 12 на завтра", sender="555"),
    )
    order = await convert_to_order(
        session,
        msg.id,
        {
            "name": "Иван",
            "phone": "+7 949 700-00-33",
            "address": "ул. Мира 12",
            "delivery_date": date.today().isoformat(),
            "bottles_pc_qty": 3,
            "total_amount": Decimal("900.00"),
        },
        actor_id=1,
    )
    assert isinstance(order, Order)
    await session.refresh(msg)
    assert msg.status == IncomingStatus.converted
    assert msg.order_id == order.id
    # клиент создан
    client = (await session.execute(select(Client))).scalar_one()
    assert client.name == "Иван"
    assert order.source_type == SourceType.telegram


async def test_convert_reuses_existing_client_by_phone(session):
    existing = Client(name="Старый", phone_primary="+7 949 700-00-44")
    session.add(existing)
    await session.flush()

    msg = await ingest_payload(session, IncomingPayload(SourceType.telegram, "вода"))
    order = await convert_to_order(
        session,
        msg.id,
        {
            "name": "Игнор",
            "phone": "8 949 700 00 44",  # тот же номер иначе записан
            "address": "ул. Новая 1",
            "delivery_date": date.today().isoformat(),
        },
        actor_id=1,
    )
    assert order.client_id == existing.id  # переиспользован


async def test_convert_validation_missing_fields(session):
    msg = await ingest_payload(session, IncomingPayload(SourceType.telegram, "вода"))
    with pytest.raises(ValidationError, match="телефон"):
        await convert_to_order(
            session, msg.id,
            {"name": "Иван", "address": "ул. А 1", "delivery_date": date.today().isoformat()},
            actor_id=1,
        )


async def test_ignore_message(session):
    msg = await ingest_payload(session, IncomingPayload(SourceType.telegram, "спам"))
    res = await ignore_message(session, msg.id)
    assert res.status == IncomingStatus.ignored


async def test_cannot_ignore_converted(session):
    msg = await ingest_payload(session, IncomingPayload(SourceType.telegram, "вода"))
    await convert_to_order(
        session, msg.id,
        {"name": "И", "phone": "+79497000055", "address": "ул. А 1",
         "delivery_date": date.today().isoformat()},
        actor_id=1,
    )
    with pytest.raises(ValidationError):
        await ignore_message(session, msg.id)


def test_mock_adapter():
    a = MockIncomingAdapter(SourceType.whatsapp)
    p = a.parse_update({"text": "привет", "sender": "x"})
    assert p.source_type == SourceType.whatsapp
    assert a.parse_update({"text": ""}) is None

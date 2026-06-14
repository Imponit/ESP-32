"""Прочие входящие каналы (MVP-3): SMS, WhatsApp, MAX, IP-телефония."""

from app.adapters.incoming import (
    WEBHOOK_ADAPTERS,
    MaxIncomingAdapter,
    PhoneIncomingAdapter,
    SmsIncomingAdapter,
    WhatsAppIncomingAdapter,
)
from app.core.enums import IncomingStatus, SourceType
from app.services.intake import ingest_payload, list_incoming


def test_sms_adapter_aliases():
    p = SmsIncomingAdapter().parse_update({"from": "+79491112233", "text": "Нужна вода"})
    assert p.source_type == SourceType.sms
    assert p.sender == "+79491112233"
    assert p.text == "Нужна вода"
    # альтернативные ключи
    p2 = SmsIncomingAdapter().parse_update({"sender": "x", "message": "2 бутыли"})
    assert p2.text == "2 бутыли"
    assert SmsIncomingAdapter().parse_update({"from": "x"}) is None  # нет текста


def test_whatsapp_cloud_api_format():
    update = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "contacts": [{"profile": {"name": "Мария"}}],
                            "messages": [
                                {
                                    "from": "79491112233",
                                    "id": "wamid.ABC",
                                    "timestamp": "1750000000",
                                    "text": {"body": "Привезите 3 бутыли"},
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    }
    p = WhatsAppIncomingAdapter().parse_update(update)
    assert p.source_type == SourceType.whatsapp
    assert p.sender == "79491112233"
    assert p.sender_name == "Мария"
    assert p.external_id == "wamid.ABC"
    assert "3 бутыли" in p.text


def test_whatsapp_simple_fallback():
    p = WhatsAppIncomingAdapter().parse_update({"from": "79491112233", "text": "вода"})
    assert p.source_type == SourceType.whatsapp
    assert p.text == "вода"
    assert WhatsAppIncomingAdapter().parse_update({"entry": [{"changes": [{"value": {}}]}]}) is None


def test_max_native_format():
    update = {
        "message": {
            "sender": {"user_id": 10, "name": "Пётр"},
            "recipient": {"chat_id": 555},
            "timestamp": 1750000000000,
            "body": {"mid": "m1", "text": "Заявка на воду"},
        }
    }
    p = MaxIncomingAdapter().parse_update(update)
    assert p.source_type == SourceType.max
    assert p.sender == "555"
    assert p.sender_name == "Пётр"
    assert p.external_id == "m1"
    assert p.text == "Заявка на воду"


def test_max_telegram_like_fallback():
    update = {"message": {"message_id": 7, "text": "вода", "chat": {"id": 9}, "from": {}}}
    p = MaxIncomingAdapter().parse_update(update)
    assert p.source_type == SourceType.max
    assert p.text == "вода"


def test_phone_adapter_synthesizes_text():
    p = PhoneIncomingAdapter().parse_update({"phone": "+79491112233"})
    assert p.source_type == SourceType.phone
    assert p.sender == "+79491112233"
    assert "Звонок от" in p.text  # текст синтезирован
    p2 = PhoneIncomingAdapter().parse_update({"caller": "+7949", "comment": "просит 5 бутылей"})
    assert p2.text == "просит 5 бутылей"
    assert PhoneIncomingAdapter().parse_update({}) is None


def test_registry_has_all_channels():
    assert set(WEBHOOK_ADAPTERS) == {"telegram", "sms", "whatsapp", "max", "phone"}


async def test_ingest_from_sms_runs_parser(session):
    payload = SmsIncomingAdapter().parse_update(
        {"from": "89491112233", "text": "3 бутыли, ул. Мира 12, завтра"}
    )
    msg = await ingest_payload(session, payload)
    assert msg.source_type == SourceType.sms
    assert msg.status == IncomingStatus.new
    f = msg.parsed["fields"]
    assert f["bottles_pc_qty"] == 3
    assert f["phone_normalized"] == "9491112233"  # из сендера


async def test_list_filter_by_source_type(session):
    await ingest_payload(
        session, SmsIncomingAdapter().parse_update({"from": "8949", "text": "a ул. Б 1"})
    )
    await ingest_payload(
        session, WhatsAppIncomingAdapter().parse_update({"from": "8949", "text": "b ул. В 2"})
    )
    _, sms_total = await list_incoming(session, source_type=SourceType.sms)
    _, wa_total = await list_incoming(session, source_type=SourceType.whatsapp)
    assert sms_total == 1
    assert wa_total == 1

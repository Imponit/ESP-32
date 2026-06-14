"""Единый интерфейс входящих каналов (SPEC.md, раздел 4/3, MVP-3).

Каждый канал (Telegram, SMS, MAX, WhatsApp, телефония, Google Sheets) реализует
IncomingChannelAdapter и приводит «сырое» обновление к IncomingPayload. Дальше
всё идёт общим путём в incoming_messages (см. services/intake.py).
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from app.core.enums import SourceType


@dataclass
class IncomingPayload:
    source_type: SourceType
    text: str
    external_id: str | None = None
    sender: str | None = None
    sender_name: str | None = None
    received_at: datetime | None = None


class IncomingChannelAdapter(Protocol):
    def parse_update(self, raw: dict) -> IncomingPayload | None: ...


class TelegramIncomingAdapter:
    """Разбор Telegram Update -> IncomingPayload. Берём текстовые сообщения."""

    source_type = SourceType.telegram

    def parse_update(self, raw: dict) -> IncomingPayload | None:
        message = raw.get("message") or raw.get("edited_message")
        if not message:
            return None
        text = message.get("text") or message.get("caption")
        if not text:
            return None
        chat = message.get("chat", {})
        frm = message.get("from", {})
        sender_name = " ".join(
            p for p in [frm.get("first_name"), frm.get("last_name")] if p
        ) or frm.get("username")
        ts = message.get("date")
        received = datetime.fromtimestamp(ts, tz=UTC) if ts else None
        return IncomingPayload(
            source_type=SourceType.telegram,
            text=text,
            external_id=str(message.get("message_id")) if message.get("message_id") else None,
            sender=str(chat.get("id")) if chat.get("id") is not None else None,
            sender_name=sender_name,
            received_at=received,
        )


def _first_present(d: dict, *keys: str):
    for k in keys:
        if d.get(k) not in (None, ""):
            return d[k]
    return None


class SmsIncomingAdapter:
    """SMS-агрегатор: ожидаем {from|sender|phone, text|message|body, id?}."""

    source_type = SourceType.sms

    def parse_update(self, raw: dict) -> IncomingPayload | None:
        text = _first_present(raw, "text", "message", "body")
        if not text:
            return None
        return IncomingPayload(
            source_type=SourceType.sms,
            text=str(text),
            external_id=_first_present(raw, "id", "message_id", "sms_id"),
            sender=_first_present(raw, "from", "sender", "phone", "msisdn"),
        )


class WhatsAppIncomingAdapter:
    """WhatsApp Cloud API: entry[].changes[].value.messages[]. Fallback — {from,text}."""

    source_type = SourceType.whatsapp

    def parse_update(self, raw: dict) -> IncomingPayload | None:
        try:
            value = raw["entry"][0]["changes"][0]["value"]
            messages = value.get("messages") or []
            if not messages:
                return None
            msg = messages[0]
            text = (msg.get("text") or {}).get("body") or msg.get("caption")
            if not text:
                return None
            contacts = value.get("contacts") or []
            name = None
            if contacts:
                name = (contacts[0].get("profile") or {}).get("name")
            ts = msg.get("timestamp")
            received = datetime.fromtimestamp(int(ts), tz=UTC) if ts else None
            return IncomingPayload(
                source_type=SourceType.whatsapp,
                text=text,
                external_id=msg.get("id"),
                sender=msg.get("from"),
                sender_name=name,
                received_at=received,
            )
        except (KeyError, IndexError, TypeError, ValueError):
            # упрощённый формат
            text = _first_present(raw, "text", "message", "body")
            if not text:
                return None
            return IncomingPayload(
                source_type=SourceType.whatsapp,
                text=str(text),
                sender=_first_present(raw, "from", "sender", "phone"),
            )


class MaxIncomingAdapter:
    """MAX (max.ru) Bot API: message.body.text / sender / recipient. Fallback — Telegram-like."""

    source_type = SourceType.max

    def parse_update(self, raw: dict) -> IncomingPayload | None:
        message = raw.get("message")
        if isinstance(message, dict) and isinstance(message.get("body"), dict):
            body = message["body"]
            text = body.get("text")
            if not text:
                return None
            sender = message.get("sender") or {}
            recipient = message.get("recipient") or {}
            ts = message.get("timestamp")
            received = datetime.fromtimestamp(int(ts) / 1000, tz=UTC) if ts else None
            chat_id = recipient.get("chat_id") or sender.get("user_id")
            return IncomingPayload(
                source_type=SourceType.max,
                text=text,
                external_id=str(body.get("mid")) if body.get("mid") else None,
                sender=str(chat_id) if chat_id is not None else None,
                sender_name=sender.get("name"),
                received_at=received,
            )
        # Telegram-подобный апдейт
        payload = TelegramIncomingAdapter().parse_update(raw)
        if payload is None:
            return None
        payload.source_type = SourceType.max
        return payload


class PhoneIncomingAdapter:
    """IP-телефония: лид по звонку {phone|caller|from, text|comment?}. Текст
    может отсутствовать — синтезируем заметку, чтобы заявка была осмысленной."""

    source_type = SourceType.phone

    def parse_update(self, raw: dict) -> IncomingPayload | None:
        sender = _first_present(raw, "phone", "caller", "from", "caller_id")
        text = _first_present(raw, "text", "comment", "note")
        if not text:
            if not sender:
                return None
            text = f"Звонок от {sender}"
        return IncomingPayload(
            source_type=SourceType.phone,
            text=str(text),
            external_id=_first_present(raw, "id", "call_id"),
            sender=str(sender) if sender else None,
        )


class MockIncomingAdapter:
    """Для тестов: оборачивает простой dict {text, sender, ...} в IncomingPayload."""

    def __init__(self, source_type: SourceType = SourceType.telegram) -> None:
        self.source_type = source_type

    def parse_update(self, raw: dict) -> IncomingPayload | None:
        if not raw.get("text"):
            return None
        return IncomingPayload(
            source_type=self.source_type,
            text=raw["text"],
            external_id=raw.get("external_id"),
            sender=raw.get("sender"),
            sender_name=raw.get("sender_name"),
            received_at=raw.get("received_at"),
        )


# Реестр вебхук-каналов: имя в URL -> адаптер
WEBHOOK_ADAPTERS: dict[str, IncomingChannelAdapter] = {
    "telegram": TelegramIncomingAdapter(),
    "sms": SmsIncomingAdapter(),
    "whatsapp": WhatsAppIncomingAdapter(),
    "max": MaxIncomingAdapter(),
    "phone": PhoneIncomingAdapter(),
}

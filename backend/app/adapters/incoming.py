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

"""Клиент Telegram для исходящих сообщений backend (отправка пакетов водителям).

Dry-run обязателен: при TELEGRAM_DRY_RUN=1 или пустом токене сообщения пишутся
в лог и проект полностью работает без реального токена.
"""

import logging
from typing import Protocol

logger = logging.getLogger("telegram.outbox")


class TelegramClient(Protocol):
    async def send_message(self, chat_id: int | None, text: str) -> None: ...


class DryRunTelegramClient:
    """Пишет исходящие сообщения в лог вместо Telegram API."""

    async def send_message(self, chat_id: int | None, text: str) -> None:
        logger.info("DRY RUN -> chat_id=%s\n%s", chat_id, text)


class MockTelegramClient:
    """Для тестов: копит сообщения в списке."""

    def __init__(self) -> None:
        self.sent: list[tuple[int | None, str]] = []

    async def send_message(self, chat_id: int | None, text: str) -> None:
        self.sent.append((chat_id, text))


class AiogramTelegramClient:
    """Боевая отправка через aiogram Bot API."""

    def __init__(self, token: str) -> None:
        from aiogram import Bot

        self._bot = Bot(token=token)

    async def send_message(self, chat_id: int | None, text: str) -> None:
        if chat_id is None:
            logger.warning("Водитель без telegram_id — сообщение не отправлено:\n%s", text)
            return
        await self._bot.send_message(chat_id, text)


def get_telegram_client() -> TelegramClient:
    from app.config import settings

    if settings.telegram_dry_run or not settings.telegram_bot_token:
        return DryRunTelegramClient()
    return AiogramTelegramClient(settings.telegram_bot_token)

"""Точка входа бота (отдельный сервис в docker compose).

Dry-run обязателен: при TELEGRAM_DRY_RUN=1 или отсутствии токена бот НЕ ходит
в Telegram API — сервис стартует, пишет это в лог и просто живёт. Проект
полностью поднимается и тестируется без реального токена.
"""

import asyncio
import logging

from app.config import settings

logger = logging.getLogger("bot")


async def run_dry() -> None:
    logger.info(
        "TELEGRAM DRY RUN: polling отключён, исходящие сообщения backend пишутся в лог. "
        "Для боевого режима задайте TELEGRAM_BOT_TOKEN и TELEGRAM_DRY_RUN=0."
    )
    while True:  # сервис живёт, чтобы compose не перезапускал его в цикле
        await asyncio.sleep(3600)


async def run_polling() -> None:
    from aiogram import Bot, Dispatcher

    from app.bot.handlers import router

    bot = Bot(token=settings.telegram_bot_token)
    dp = Dispatcher()
    dp.include_router(router)
    logger.info("Бот запущен (polling)")
    await dp.start_polling(bot)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    if settings.telegram_dry_run or not settings.telegram_bot_token:
        asyncio.run(run_dry())
    else:
        asyncio.run(run_polling())


if __name__ == "__main__":
    main()

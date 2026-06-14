"""Конфигурация приложения. Все секреты — только из переменных окружения (.env)."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://water:water_dev_password@localhost:5432/water_crm"
    jwt_secret: str = "dev_secret_do_not_use_in_production"
    jwt_expires_hours: int = 12
    cors_origins: str = "http://localhost:5173,http://localhost:8080"
    telegram_dry_run: bool = True
    telegram_bot_token: str = ""
    # Секрет для вебхука входящих заявок Telegram (MVP-3). Пусто — вебхук выключен.
    telegram_webhook_secret: str = ""
    # CSV-экспорт Google Sheets для синхронизации заявок (MVP-3). Пусто — выключено.
    # Пример: https://docs.google.com/spreadsheets/d/<ID>/export?format=csv&gid=<GID>
    google_sheets_csv_url: str = ""

    # Дефолты; рабочие значения читаются из таблицы settings
    default_timezone: str = "Europe/Moscow"
    default_max_route_points: int = 9

    # Геокодер (MVP-2). Ключ — только из .env; параметры — в таблице settings.
    yandex_geocoder_api_key: str = ""
    yandex_geocoder_url: str = "https://geocode-maps.yandex.ru/1.x/"
    # Порог точности: результат ниже — заказ отправляется диспетчеру в needs_review
    default_geocode_confidence_threshold: float = 0.7

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()

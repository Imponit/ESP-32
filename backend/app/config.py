"""Конфигурация приложения. Все секреты — только из переменных окружения (.env)."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://water:water_dev_password@localhost:5432/water_crm"
    jwt_secret: str = "dev_secret_do_not_use_in_production"
    jwt_expires_hours: int = 12
    cors_origins: str = "http://localhost:5173,http://localhost:8080"
    telegram_dry_run: bool = True
    telegram_bot_token: str = ""

    # Дефолты; рабочие значения читаются из таблицы settings
    default_timezone: str = "Europe/Moscow"
    default_max_route_points: int = 9

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()

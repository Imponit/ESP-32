"""Чтение/запись таблицы settings (ключ-значение JSON)."""

from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings as env_settings
from app.models import Setting

KEY_MAX_ROUTE_POINTS = "max_route_points"
KEY_TIMEZONE = "timezone"
# TODO MVP-2: правила баллов (scoring_rules), параметры геокодера (geocoder)


async def get_setting(session: AsyncSession, key: str, default: Any = None) -> Any:
    row = await session.get(Setting, key)
    return row.value if row is not None else default


async def set_setting(session: AsyncSession, key: str, value: Any) -> None:
    row = await session.get(Setting, key)
    if row is None:
        session.add(Setting(key=key, value=value))
    else:
        row.value = value


async def get_max_route_points(session: AsyncSession) -> int:
    return int(
        await get_setting(session, KEY_MAX_ROUTE_POINTS, env_settings.default_max_route_points)
    )


async def get_timezone(session: AsyncSession) -> ZoneInfo:
    name = await get_setting(session, KEY_TIMEZONE, env_settings.default_timezone)
    return ZoneInfo(str(name))

"""Геокодер (SPEC.md, раздел 11). Интерфейс — MVP-1, реализация Яндекса — MVP-2.

Ручная правка координат доступна всегда (MVP-1). Все запросы к провайдеру
логируются. При недоступности провайдера поднимается GeocoderUnavailableError —
сервис не теряет заказ, а ставит geocode_status=pending|failed.
"""

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

import httpx

logger = logging.getLogger("geocoder")


@dataclass
class GeocodeResult:
    latitude: Decimal
    longitude: Decimal
    normalized_address: str
    confidence: Decimal  # 0..1
    precision: str  # сырая точность провайдера (exact|number|near|street|...)


class GeocoderUnavailableError(Exception):
    """Провайдер недоступен (сеть/таймаут/5xx/неверный ключ) — заказ не теряем."""


# Точность Яндекс.Геокодера -> наша уверенность 0..1
YANDEX_PRECISION_CONFIDENCE: dict[str, Decimal] = {
    "exact": Decimal("1.000"),
    "number": Decimal("0.900"),
    "near": Decimal("0.700"),
    "range": Decimal("0.600"),
    "street": Decimal("0.500"),
    "other": Decimal("0.300"),
}


class GeocoderProvider(Protocol):
    async def geocode(self, address: str) -> GeocodeResult | None: ...


class MockGeocoderProvider:
    """Для тестов: возвращает заранее заданные результаты, считает вызовы.

    Если в fail_for указан адрес — имитирует недоступность провайдера.
    """

    def __init__(
        self,
        results: dict[str, GeocodeResult] | None = None,
        fail_for: set[str] | None = None,
    ) -> None:
        self.results = results or {}
        self.fail_for = fail_for or set()
        self.calls: list[str] = []

    async def geocode(self, address: str) -> GeocodeResult | None:
        self.calls.append(address)
        if address in self.fail_for:
            raise GeocoderUnavailableError(f"Mock: провайдер недоступен для {address!r}")
        return self.results.get(address)


class YandexGeocoderProvider:
    """HTTP-запросы к Яндекс.Геокодеру (https://geocode-maps.yandex.ru/1.x/).

    Возвращает None, если адрес не найден; бросает GeocoderUnavailableError при
    сетевых проблемах/5xx/неверном ключе.
    """

    def __init__(self, api_key: str, url: str, timeout: float = 5.0) -> None:
        self._api_key = api_key
        self._url = url
        self._timeout = timeout

    async def geocode(self, address: str) -> GeocodeResult | None:
        params = {
            "apikey": self._api_key,
            "geocode": address,
            "format": "json",
            "results": "1",
            "lang": "ru_RU",
        }
        logger.info("Геокодинг запрос: %s", address)
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(self._url, params=params)
        except httpx.HTTPError as e:
            logger.warning("Геокодер недоступен (сеть): %s", e)
            raise GeocoderUnavailableError(str(e)) from e

        if resp.status_code != 200:
            logger.warning("Геокодер ответил %s для %s", resp.status_code, address)
            raise GeocoderUnavailableError(f"HTTP {resp.status_code}")

        return self._parse(resp.json())

    @staticmethod
    def _parse(data: dict) -> GeocodeResult | None:
        try:
            members = data["response"]["GeoObjectCollection"]["featureMember"]
        except (KeyError, TypeError) as e:
            raise GeocoderUnavailableError(f"Неожиданный ответ геокодера: {e}") from e
        if not members:
            return None  # адрес не найден
        obj = members[0]["GeoObject"]
        lon_str, lat_str = obj["Point"]["pos"].split()
        meta = obj["metaDataProperty"]["GeocoderMetaData"]
        precision = meta.get("precision", "other")
        return GeocodeResult(
            latitude=Decimal(lat_str),
            longitude=Decimal(lon_str),
            normalized_address=meta.get("text", ""),
            confidence=YANDEX_PRECISION_CONFIDENCE.get(precision, Decimal("0.300")),
            precision=precision,
        )


def get_geocoder() -> GeocoderProvider | None:
    """Боевой геокодер из настроек окружения. None — ключ не задан (геокодинг выключен)."""
    from app.config import settings

    if not settings.yandex_geocoder_api_key:
        return None
    return YandexGeocoderProvider(
        settings.yandex_geocoder_api_key, settings.yandex_geocoder_url
    )

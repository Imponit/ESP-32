"""Интерфейс геокодера (SPEC.md, раздел 11). Реализация — MVP-2.

В MVP-1 координаты вводятся вручную (geocode_status = manual).
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol


@dataclass
class GeocodeResult:
    latitude: Decimal
    longitude: Decimal
    normalized_address: str
    confidence: Decimal  # 0..1


class GeocoderProvider(Protocol):
    async def geocode(self, address: str) -> GeocodeResult | None: ...


class MockGeocoderProvider:
    """Для тестов: возвращает заранее заданные результаты."""

    def __init__(self, results: dict[str, GeocodeResult] | None = None) -> None:
        self.results = results or {}
        self.calls: list[str] = []

    async def geocode(self, address: str) -> GeocodeResult | None:
        self.calls.append(address)
        return self.results.get(address)


class YandexGeocoderProvider:
    """TODO MVP-2: HTTP-запросы к Яндекс.Геокодеру, кэш geocode_cache,
    логирование запросов, обработка недоступности (geocode_status=pending|failed)."""

    async def geocode(self, address: str) -> GeocodeResult | None:
        raise NotImplementedError("Геокодинг реализуется в MVP-2")

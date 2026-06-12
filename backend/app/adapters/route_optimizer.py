"""Интерфейс оптимизации маршрута (SPEC.md, раздел 12).

MVP-1 — SimpleRouteOptimizer (порядок диспетчера). OR-Tools/Яндекс — MVP-3.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol


@dataclass
class RoutePoint:
    order_id: int
    latitude: Decimal | None
    longitude: Decimal | None


class RouteOptimizer(Protocol):
    def optimize(self, points: list[RoutePoint]) -> list[RoutePoint]: ...


class SimpleRouteOptimizer:
    """Без оптимизации: порядок точек = порядок, заданный диспетчером."""

    def optimize(self, points: list[RoutePoint]) -> list[RoutePoint]:
        return list(points)


class OrToolsRouteOptimizer:
    """TODO MVP-3: оптимизация OR-Tools (временные окна, вместимость, срочность)."""

    def optimize(self, points: list[RoutePoint]) -> list[RoutePoint]:
        raise NotImplementedError("OR-Tools оптимизация — MVP-3")


class YandexRouteOptimizer:
    """TODO MVP-3: Yandex Route Optimization API."""

    def optimize(self, points: list[RoutePoint]) -> list[RoutePoint]:
        raise NotImplementedError("Яндекс-оптимизация — MVP-3")

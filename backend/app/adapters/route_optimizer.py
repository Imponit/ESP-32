"""Оптимизация порядка точек маршрута (SPEC.md, раздел 12).

- SimpleRouteOptimizer — без оптимизации (порядок диспетчера), MVP-1;
- GreedyRouteOptimizer — ближайший сосед по гео-расстоянию, MVP-3;
- OrTools/Yandex — интерфейсные заглушки (тяжёлые зависимости/внешний API,
  включаются при подключении).

Точки без координат не участвуют в оптимизации и добавляются в конец, сохраняя
относительный порядок диспетчера.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from app.core.geo import haversine_km


@dataclass
class RoutePoint:
    order_id: int
    latitude: Decimal | None
    longitude: Decimal | None

    @property
    def has_coords(self) -> bool:
        return self.latitude is not None and self.longitude is not None


class RouteOptimizer(Protocol):
    def optimize(self, points: list[RoutePoint]) -> list[RoutePoint]: ...


def _split_coords(points: list[RoutePoint]) -> tuple[list[RoutePoint], list[RoutePoint]]:
    with_coords = [p for p in points if p.has_coords]
    without = [p for p in points if not p.has_coords]
    return with_coords, without


class SimpleRouteOptimizer:
    """Без оптимизации: порядок точек = порядок, заданный диспетчером."""

    def optimize(self, points: list[RoutePoint]) -> list[RoutePoint]:
        return list(points)


class GreedyRouteOptimizer:
    """Эвристика «ближайший сосед»: стартуем с первой точки диспетчера, затем
    каждый раз идём в ближайшую ещё не посещённую. Точки без координат — в конец."""

    def optimize(self, points: list[RoutePoint]) -> list[RoutePoint]:
        with_coords, without = _split_coords(points)
        if len(with_coords) <= 2:
            return with_coords + without
        remaining = with_coords[:]
        route = [remaining.pop(0)]
        while remaining:
            last = route[-1]
            nxt = min(
                remaining,
                key=lambda p: haversine_km(last.latitude, last.longitude, p.latitude, p.longitude),
            )
            route.append(nxt)
            remaining.remove(nxt)
        return route + without


class OrToolsRouteOptimizer:
    """TODO: оптимизация OR-Tools (временные окна, вместимость, срочность).
    Требует пакет ortools; включается при подключении."""

    def optimize(self, points: list[RoutePoint]) -> list[RoutePoint]:
        raise NotImplementedError("OR-Tools оптимизация — требует пакет ortools")


class YandexRouteOptimizer:
    """TODO: Yandex Route Optimization API. Требует API-ключ; включается при подключении."""

    def optimize(self, points: list[RoutePoint]) -> list[RoutePoint]:
        raise NotImplementedError("Яндекс-оптимизация — требует API-ключ")


_OPTIMIZERS: dict[str, RouteOptimizer] = {
    "simple": SimpleRouteOptimizer(),
    "greedy": GreedyRouteOptimizer(),
    "ortools": OrToolsRouteOptimizer(),
    "yandex": YandexRouteOptimizer(),
}


def get_route_optimizer(name: str) -> RouteOptimizer:
    optimizer = _OPTIMIZERS.get(name)
    if optimizer is None:
        raise ValueError(f"Неизвестный оптимизатор маршрута: {name}")
    return optimizer

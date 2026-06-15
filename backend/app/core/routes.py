"""Генерация ссылок Яндекс.Карт (SPEC.md, раздел 12). Чистые функции, без I/O."""

from decimal import Decimal
from urllib.parse import quote


def point_link(
    latitude: Decimal | float | None,
    longitude: Decimal | float | None,
    address_text: str = "",
) -> str | None:
    """Ссылка на одну точку: по координатам, при их отсутствии — по тексту адреса."""
    if latitude is not None and longitude is not None:
        return f"https://yandex.ru/maps/?pt={longitude},{latitude}&z=17&l=map"
    if address_text:
        return f"https://yandex.ru/maps/?text={quote(address_text)}"
    return None


def route_link(points: list[tuple[Decimal | float, Decimal | float]]) -> str | None:
    """Ссылка на маршрут по координатам, в порядке диспетчера (route_position).

    Точки — (latitude, longitude). Пустой список -> None.
    Лимит количества точек проверяет сервис планирования (max_route_points).
    """
    if not points:
        return None
    rtext = "~".join(f"{lat},{lon}" for lat, lon in points)
    return f"https://yandex.ru/maps/?rtext={rtext}&rtt=auto"

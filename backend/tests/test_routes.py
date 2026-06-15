"""Генерация ссылок Яндекс.Карт."""

from decimal import Decimal

from app.core.routes import point_link, route_link


def test_point_link_with_coords():
    url = point_link(Decimal("47.097133"), Decimal("37.543367"))
    assert url == "https://yandex.ru/maps/?pt=37.543367,47.097133&z=17&l=map"


def test_point_link_without_coords_uses_address_text():
    url = point_link(None, None, "пр. Мира, 12")
    assert url is not None
    assert url.startswith("https://yandex.ru/maps/?text=")
    assert "%20" in url or "+" in url  # адрес закодирован


def test_point_link_nothing():
    assert point_link(None, None, "") is None


def test_route_link_order_preserved():
    pts = [(Decimal("47.10"), Decimal("37.54")), (Decimal("47.11"), Decimal("37.55"))]
    url = route_link(pts)
    assert url == "https://yandex.ru/maps/?rtext=47.10,37.54~47.11,37.55&rtt=auto"


def test_route_link_empty():
    assert route_link([]) is None

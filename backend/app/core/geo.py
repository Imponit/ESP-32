"""Гео-расчёты (чистые функции, без I/O)."""

import math
from decimal import Decimal

EARTH_RADIUS_KM = 6371.0088


def haversine_km(
    lat1: Decimal | float,
    lon1: Decimal | float,
    lat2: Decimal | float,
    lon2: Decimal | float,
) -> float:
    """Расстояние по большому кругу между двумя точками, км."""
    rlat1, rlon1, rlat2, rlon2 = (
        math.radians(float(lat1)),
        math.radians(float(lon1)),
        math.radians(float(lat2)),
        math.radians(float(lon2)),
    )
    dlat = rlat2 - rlat1
    dlon = rlon2 - rlon1
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))

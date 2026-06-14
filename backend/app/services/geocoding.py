"""Сервис геокодинга (SPEC.md, раздел 11, MVP-2).

Правила:
- кэш по нормализованному адресу (geocode_cache);
- если координаты уже есть — повторно не геокодировать (кроме force);
- ручную правку координат (geocode_status=manual) не перетираем;
- неточный результат (confidence < порога) — связанные заказы в `new` уходят
  в `needs_review` (очередь проверки диспетчером);
- провайдер недоступен — заказ не теряется: geocode_status=pending;
- адрес не найден — geocode_status=failed;
- все запросы к провайдеру логируются (в адаптере).
"""

import logging
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.geocoder import (
    GeocodeResult,
    GeocoderProvider,
    GeocoderUnavailableError,
)
from app.core.enums import ActorType, GeocodeStatus, OrderStatus
from app.models import Address, GeocodeCache, Order
from app.services.app_settings import get_geocode_confidence_threshold
from app.services.orders import transition_order

logger = logging.getLogger("geocoding")


def normalize_address(raw: str) -> str:
    """Ключ кэша: нижний регистр, схлопнутые пробелы, без хвостовой пунктуации."""
    text = re.sub(r"\s+", " ", raw.strip().lower())
    return text.strip(" .,;")


async def _flag_orders_needs_review(session: AsyncSession, address_id: int) -> list[int]:
    """Неточная геопозиция — заказы этого адреса в статусе `new` уходят в needs_review."""
    orders = (
        (
            await session.execute(
                select(Order).where(
                    Order.address_id == address_id, Order.status == OrderStatus.new
                )
            )
        )
        .scalars()
        .all()
    )
    flagged = []
    for order in orders:
        await transition_order(
            session,
            order,
            OrderStatus.needs_review,
            ActorType.system,
            comment="Неточная геопозиция — требуется проверка адреса",
        )
        flagged.append(order.id)
    return flagged


async def _apply_result(
    session: AsyncSession,
    address: Address,
    result: GeocodeResult,
    threshold: float,
    from_cache: bool,
) -> dict:
    address.latitude = result.latitude
    address.longitude = result.longitude
    address.normalized_address = result.normalized_address or address.normalized_address
    address.geocode_confidence = result.confidence
    address.geocode_status = GeocodeStatus.ok
    await session.flush()

    needs_review: list[int] = []
    imprecise = float(result.confidence) < threshold
    if imprecise:
        needs_review = await _flag_orders_needs_review(session, address.id)
    return {
        "address_id": address.id,
        "status": "ok",
        "latitude": str(result.latitude),
        "longitude": str(result.longitude),
        "confidence": str(result.confidence),
        "precision": result.precision,
        "from_cache": from_cache,
        "imprecise": imprecise,
        "needs_review_order_ids": needs_review,
    }


async def geocode_address(
    session: AsyncSession,
    address: Address,
    provider: GeocoderProvider,
    force: bool = False,
) -> dict:
    """Геокодирует один адрес. provider не должен быть None (проверка — в роуте)."""
    # Ручные координаты не трогаем без force
    if address.geocode_status == GeocodeStatus.manual and not force:
        return {"address_id": address.id, "status": "skipped_manual", "from_cache": False}
    # Координаты уже есть — повторно не геокодируем (кроме force)
    if address.latitude is not None and address.longitude is not None and not force:
        return {"address_id": address.id, "status": "already_has_coords", "from_cache": False}

    threshold = await get_geocode_confidence_threshold(session)
    key = normalize_address(address.raw_address)

    cached = (
        await session.execute(select(GeocodeCache).where(GeocodeCache.query_normalized == key))
    ).scalar_one_or_none()
    if cached is not None:
        result = GeocodeResult(
            latitude=cached.latitude,
            longitude=cached.longitude,
            normalized_address=cached.normalized_address or "",
            confidence=cached.confidence,
            precision=cached.precision or "other",
        )
        return await _apply_result(session, address, result, threshold, from_cache=True)

    try:
        result = await provider.geocode(address.raw_address)
    except GeocoderUnavailableError:
        # Провайдер недоступен — данные не теряем, пометим pending для повторной попытки
        address.geocode_status = GeocodeStatus.pending
        await session.flush()
        logger.warning("Геокодер недоступен, адрес %s -> pending", address.id)
        return {"address_id": address.id, "status": "pending", "from_cache": False}

    if result is None:
        address.geocode_status = GeocodeStatus.failed
        await session.flush()
        logger.info("Адрес не найден геокодером: %s", address.raw_address)
        return {"address_id": address.id, "status": "failed", "from_cache": False}

    session.add(
        GeocodeCache(
            query_normalized=key,
            latitude=result.latitude,
            longitude=result.longitude,
            precision=result.precision,
            confidence=result.confidence,
            normalized_address=result.normalized_address,
            provider="yandex",
        )
    )
    return await _apply_result(session, address, result, threshold, from_cache=False)

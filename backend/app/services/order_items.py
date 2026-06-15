"""Позиции заказа и каталог (SPEC.md, раздел 3 MVP-3).

order_items вводится как дополнительный слой: на каждый заказ всегда формируются
позиции. Если переданы явные items — из них; иначе из фиксированных полей
количества (bottles_pc/pet/pumps) по каталогу. Фиксированные поля остаются как
денормализованный кэш для отчётов/кассы/вместимости и держатся в синхроне с items.
"""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ProductKind
from app.models import Order, OrderItem, Product
from app.services.errors import NotFoundError, ValidationError

# kind -> поле количества в заказе
_KIND_TO_QTY_FIELD = {
    ProductKind.bottle_pc: "bottles_pc_qty",
    ProductKind.bottle_pet: "bottles_pet_qty",
    ProductKind.pump: "pumps_qty",
}
_DEFAULT_NAME = {
    ProductKind.bottle_pc: "Вода 19 л (поликарбонат)",
    ProductKind.bottle_pet: "Вода 19 л (ПЭТ)",
    ProductKind.pump: "Помпа",
}


async def _catalog_by_kind(session: AsyncSession) -> dict[ProductKind, Product]:
    products = (
        (await session.execute(select(Product).where(Product.is_active.is_(True))))
        .scalars()
        .all()
    )
    by_kind: dict[ProductKind, Product] = {}
    for p in products:
        by_kind.setdefault(p.kind, p)  # первый активный товар каждого вида
    return by_kind


async def build_items_for_order(
    session: AsyncSession, order: Order, items_data: list[dict] | None
) -> list[OrderItem]:
    """Сформировать позиции заказа. items_data=None — из количеств по каталогу."""
    if items_data:
        items = await _items_from_explicit(session, order, items_data)
        # количества и сумма заказа выводятся из позиций
        order.bottles_pc_qty = _qty_for(items, ProductKind.bottle_pc)
        order.bottles_pet_qty = _qty_for(items, ProductKind.bottle_pet)
        order.pumps_qty = _qty_for(items, ProductKind.pump)
        order.total_amount = sum((i.amount for i in items), Decimal("0.00"))
    else:
        items = await _items_from_quantities(session, order)
        # сумму считаем из каталога только если диспетчер не задал её явно
        if not order.total_amount or order.total_amount == 0:
            order.total_amount = sum((i.amount for i in items), Decimal("0.00"))
    for it in items:
        session.add(it)
    await session.flush()
    return items


async def _items_from_explicit(
    session: AsyncSession, order: Order, items_data: list[dict]
) -> list[OrderItem]:
    items = []
    for raw in items_data:
        qty = int(raw.get("qty") or 0)
        if qty <= 0:
            raise ValidationError("Количество позиции должно быть больше нуля")
        product = None
        if raw.get("product_id") is not None:
            product = await session.get(Product, raw["product_id"])
            if product is None:
                raise NotFoundError(f"Товар {raw['product_id']} не найден")
        name = (raw.get("name") or (product.name if product else "")).strip()
        if not name:
            raise ValidationError("У позиции нет наименования")
        kind = ProductKind(raw["kind"]) if raw.get("kind") else (
            product.kind if product else ProductKind.other
        )
        unit_price = (
            Decimal(str(raw["unit_price"]))
            if raw.get("unit_price") is not None
            else (product.unit_price if product else Decimal("0.00"))
        )
        items.append(
            OrderItem(
                order_id=order.id,
                product_id=product.id if product else None,
                name=name,
                kind=kind,
                qty=qty,
                unit_price=unit_price,
                amount=unit_price * qty,
            )
        )
    return items


async def _items_from_quantities(session: AsyncSession, order: Order) -> list[OrderItem]:
    catalog = await _catalog_by_kind(session)
    items = []
    for kind, field in _KIND_TO_QTY_FIELD.items():
        qty = getattr(order, field) or 0
        if qty <= 0:
            continue
        product = catalog.get(kind)
        unit_price = product.unit_price if product else Decimal("0.00")
        items.append(
            OrderItem(
                order_id=order.id,
                product_id=product.id if product else None,
                name=product.name if product else _DEFAULT_NAME[kind],
                kind=kind,
                qty=qty,
                unit_price=unit_price,
                amount=unit_price * qty,
            )
        )
    return items


def _qty_for(items: list[OrderItem], kind: ProductKind) -> int:
    return sum(i.qty for i in items if i.kind == kind)


async def list_order_items(session: AsyncSession, order_id: int) -> list[OrderItem]:
    return list(
        (
            await session.execute(
                select(OrderItem).where(OrderItem.order_id == order_id).order_by(OrderItem.id)
            )
        )
        .scalars()
        .all()
    )

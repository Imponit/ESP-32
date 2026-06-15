from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api.deps import CurrentUser, SessionDep
from app.api.schemas import ProductIn, ProductOut, ProductPatch
from app.models import Product

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=list[ProductOut])
async def list_products(session: SessionDep, _: CurrentUser, include_inactive: bool = True):
    q = select(Product).order_by(Product.sort_order, Product.id)
    if not include_inactive:
        q = q.where(Product.is_active.is_(True))
    return list((await session.execute(q)).scalars().all())


@router.post("", response_model=ProductOut, status_code=201)
async def create_product(body: ProductIn, session: SessionDep, _: CurrentUser):
    product = Product(**body.model_dump())
    session.add(product)
    await session.commit()
    return product


@router.patch("/{product_id}", response_model=ProductOut)
async def patch_product(product_id: int, body: ProductPatch, session: SessionDep, _: CurrentUser):
    product = await session.get(Product, product_id)
    if product is None:
        raise HTTPException(404, "Товар не найден")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(product, k, v)
    await session.commit()
    return product

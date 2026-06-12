from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api.deps import CurrentUser, SessionDep
from app.api.schemas import DriverIn, DriverOut, DriverPatch
from app.models import Driver

router = APIRouter(prefix="/drivers", tags=["drivers"])


@router.get("", response_model=list[DriverOut])
async def list_drivers(session: SessionDep, _: CurrentUser, include_inactive: bool = True):
    q = select(Driver).order_by(Driver.id)
    if not include_inactive:
        q = q.where(Driver.is_active.is_(True))
    return list((await session.execute(q)).scalars().all())


@router.post("", response_model=DriverOut, status_code=201)
async def create_driver(body: DriverIn, session: SessionDep, _: CurrentUser):
    driver = Driver(**body.model_dump())
    session.add(driver)
    await session.commit()
    return driver


@router.patch("/{driver_id}", response_model=DriverOut)
async def patch_driver(driver_id: int, body: DriverPatch, session: SessionDep, _: CurrentUser):
    """Правка водителя: активация/деактивация, привязка Telegram ID вручную и т.д."""
    driver = await session.get(Driver, driver_id)
    if driver is None:
        raise HTTPException(404, "Водитель не найден")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(driver, k, v)
    await session.commit()
    return driver

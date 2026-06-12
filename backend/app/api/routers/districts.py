from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api.deps import CurrentUser, SessionDep
from app.api.schemas import DistrictIn, DistrictOut, DistrictPatch
from app.models import District

router = APIRouter(prefix="/districts", tags=["districts"])


@router.get("", response_model=list[DistrictOut])
async def list_districts(session: SessionDep, _: CurrentUser):
    rows = await session.execute(select(District).order_by(District.sort_order, District.id))
    return list(rows.scalars().all())


@router.post("", response_model=DistrictOut, status_code=201)
async def create_district(body: DistrictIn, session: SessionDep, _: CurrentUser):
    district = District(**body.model_dump())
    session.add(district)
    await session.commit()
    return district


@router.patch("/{district_id}", response_model=DistrictOut)
async def patch_district(
    district_id: int, body: DistrictPatch, session: SessionDep, _: CurrentUser
):
    district = await session.get(District, district_id)
    if district is None:
        raise HTTPException(404, "Район не найден")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(district, k, v)
    await session.commit()
    return district

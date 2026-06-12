from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import AdminUser, CurrentUser, SessionDep
from app.api.schemas import SettingOut, SettingPatch
from app.models import Setting
from app.services.app_settings import set_setting

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=list[SettingOut])
async def list_settings(session: SessionDep, _: CurrentUser):
    rows = (await session.execute(select(Setting))).scalars().all()
    return [SettingOut(key=s.key, value=s.value) for s in rows]


@router.put("/{key}", response_model=SettingOut)
async def put_setting(key: str, body: SettingPatch, session: SessionDep, _: AdminUser):
    await set_setting(session, key, body.value)
    await session.commit()
    return SettingOut(key=key, value=body.value)

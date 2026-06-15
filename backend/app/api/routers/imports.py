from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from app.api.deps import CurrentUser, SessionDep
from app.api.schemas import ImportReportOut
from app.services.importing import ImportError_, import_orders

router = APIRouter(prefix="/import", tags=["import"])


@router.post("/orders", response_model=ImportReportOut)
async def import_orders_endpoint(
    session: SessionDep,
    user: CurrentUser,
    file: Annotated[UploadFile, File()],
    dry_run: Annotated[bool, Query(description="Предпросмотр без сохранения")] = False,
):
    """Импорт заказов из CSV/XLSX (MVP-2). dry_run=1 — проверить файл без записи.

    Обязательные колонки: имя, телефон, адрес, дата. Опциональные: район, широта,
    долгота, подъезд, этаж, часть_дня, бутыли_пк, бутыли_пэт, помпы, сумма, оплата,
    комментарий. Ошибочные строки попадают в отчёт, остальные импортируются.
    """
    content = await file.read()
    try:
        report = await import_orders(
            session, file.filename or "", content, actor_id=user.id, dry_run=dry_run
        )
    except ImportError_ as e:
        raise HTTPException(400, str(e)) from e
    return asdict(report)

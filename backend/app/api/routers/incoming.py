from fastapi import APIRouter, HTTPException, Query

from app.adapters.google_sheets import (
    GoogleSheetsUnavailableError,
    get_google_sheets_adapter,
)
from app.adapters.incoming import (
    WEBHOOK_ADAPTERS,
    IncomingPayload,
    TelegramIncomingAdapter,
)
from app.api.deps import CurrentUser, SessionDep
from app.api.schemas import (
    IncomingConvertRequest,
    IncomingIn,
    IncomingListOut,
    IncomingOut,
    OrderOut,
)
from app.config import settings
from app.core.enums import IncomingStatus, SourceType
from app.services.intake import (
    convert_to_order,
    get_incoming,
    ignore_message,
    ingest_payload,
    list_incoming,
)
from app.services.sheets_intake import sync_google_sheet

router = APIRouter(prefix="/incoming", tags=["incoming"])

_telegram_adapter = TelegramIncomingAdapter()


@router.post("", response_model=IncomingOut, status_code=201)
async def intake_generic(body: IncomingIn, session: SessionDep, _: CurrentUser):
    """Принять входящую заявку (универсальный intake, в т.ч. для тестов и каналов
    без вебхука). Текст разбирается авто-парсером в черновик."""
    payload = IncomingPayload(
        source_type=body.source_type,
        text=body.text,
        sender=body.sender,
        sender_name=body.sender_name,
        external_id=body.external_id,
    )
    msg = await ingest_payload(session, payload)
    await session.commit()
    return msg


@router.post("/telegram/webhook/{secret}", status_code=202)
async def telegram_webhook(secret: str, update: dict, session: SessionDep):
    """Вебхук Telegram для входящих заявок клиентов (MVP-3).

    Без JWT (Telegram не умеет), защита — секрет в пути (TELEGRAM_WEBHOOK_SECRET).
    Нераспознанные апдейты игнорируются (202).
    """
    if not settings.telegram_webhook_secret:
        raise HTTPException(503, "Вебхук не настроен (нет TELEGRAM_WEBHOOK_SECRET)")
    if secret != settings.telegram_webhook_secret:
        raise HTTPException(403, "Неверный секрет вебхука")
    payload = _telegram_adapter.parse_update(update)
    if payload is None:
        return {"ok": True, "ingested": False}
    await ingest_payload(session, payload)
    await session.commit()
    return {"ok": True, "ingested": True}


@router.post("/webhook/{channel}/{secret}", status_code=202)
async def channel_webhook(channel: str, secret: str, update: dict, session: SessionDep):
    """Универсальный вебхук входящих каналов (SMS/MAX/WhatsApp/телефония/Telegram).

    Без JWT (провайдеры не умеют), защита — общий секрет INCOMING_WEBHOOK_SECRET.
    Нераспознанные апдейты игнорируются (202).
    """
    if not settings.incoming_webhook_secret:
        raise HTTPException(503, "Вебхук не настроен (нет INCOMING_WEBHOOK_SECRET)")
    if secret != settings.incoming_webhook_secret:
        raise HTTPException(403, "Неверный секрет вебхука")
    adapter = WEBHOOK_ADAPTERS.get(channel)
    if adapter is None:
        raise HTTPException(404, f"Неизвестный канал: {channel}")
    payload = adapter.parse_update(update)
    if payload is None:
        return {"ok": True, "ingested": False}
    await ingest_payload(session, payload)
    await session.commit()
    return {"ok": True, "ingested": True, "channel": channel}


@router.post("/google-sheets/sync")
async def google_sheets_sync(session: SessionDep, _: CurrentUser) -> dict:
    """Синхронизировать заявки из Google Sheets (MVP-3). Новые строки -> очередь
    черновиков; уже принятые строки пропускаются."""
    adapter = get_google_sheets_adapter()
    if adapter is None:
        raise HTTPException(503, "Google Sheets не настроен (нет GOOGLE_SHEETS_CSV_URL)")
    try:
        result = await sync_google_sheet(session, adapter)
    except GoogleSheetsUnavailableError as e:
        raise HTTPException(502, f"Google Sheets недоступен: {e}") from e
    await session.commit()
    return result


@router.get("", response_model=IncomingListOut)
async def list_messages(
    session: SessionDep,
    _: CurrentUser,
    status: IncomingStatus | None = None,
    source_type: SourceType | None = None,
    limit: int = Query(100, le=500),
    offset: int = 0,
):
    items, total = await list_incoming(session, status, source_type, limit, offset)
    return IncomingListOut(items=items, total=total, limit=limit, offset=offset)


@router.get("/{message_id}", response_model=IncomingOut)
async def get_message(message_id: int, session: SessionDep, _: CurrentUser):
    return await get_incoming(session, message_id)


@router.post("/{message_id}/convert", response_model=OrderOut, status_code=201)
async def convert(
    message_id: int, body: IncomingConvertRequest, session: SessionDep, user: CurrentUser
):
    """Создать заказ из заявки (поля проверены диспетчером)."""
    order = await convert_to_order(session, message_id, body.model_dump(), user.id)
    await session.commit()
    return order


@router.post("/{message_id}/ignore", response_model=IncomingOut)
async def ignore(message_id: int, session: SessionDep, _: CurrentUser):
    msg = await ignore_message(session, message_id)
    await session.commit()
    return msg

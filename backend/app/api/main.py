"""FastAPI-приложение: роуты, CORS, маппинг доменных ошибок в HTTP."""

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routers import auth, clients, districts, drivers, imports, orders, planning, reports
from app.api.routers import settings as settings_router
from app.config import settings
from app.core.state_machine import TransitionError
from app.services.errors import NotFoundError, ValidationError

logging.basicConfig(level=logging.INFO)


def create_app() -> FastAPI:
    app = FastAPI(
        title="CRM доставки воды 19 л",
        description="Диспетчерская система: заказы, планирование, Telegram-бот водителей, касса",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(NotFoundError)
    async def not_found_handler(request: Request, exc: NotFoundError):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ValidationError)
    async def validation_handler(request: Request, exc: ValidationError):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(TransitionError)
    async def transition_handler(request: Request, exc: TransitionError):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    for router in (
        auth.router,
        districts.router,
        clients.router,
        orders.router,
        drivers.router,
        planning.router,
        reports.router,
        imports.router,
        settings_router.router,
    ):
        app.include_router(router)

    @app.get("/health", tags=["health"])
    async def health():
        return {"status": "ok"}

    return app


app = create_app()

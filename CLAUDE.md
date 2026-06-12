# CRM доставки воды 19 л

Диспетчерская система: заказы, планирование по районам и водителям, Telegram-бот водителей, касса. Полная спецификация — в @SPEC.md. Принятые решения — в @ASSUMPTIONS.md.

## Объём работ

Реализуем только **MVP-1** (SPEC.md, раздел 3). Для MVP-2/3 — интерфейсы и TODO, без реализации.

## Стек (зафиксирован, не менять)

- Python 3.12+, FastAPI; PostgreSQL 16 **без PostGIS**; SQLAlchemy 2 + Alembic
- Бот: aiogram 3, отдельный сервис. Frontend: React + Vite SPA (не Next.js)
- **Без Celery/RQ/Redis** — фоновые задачи через BackgroundTasks/asyncio-воркер
- Docker Compose: db, backend, bot, frontend

## Команды

- `make up` / `make migrate` / `make seed` / `make test`
- Линтер: ruff

## Правила

- Статусы заказов меняются **только** через машину состояний в service layer; каждый переход пишет запись в `order_events`.
- Бот в разработке и тестах — только `TELEGRAM_DRY_RUN=1`, без реального токена.
- Снапшот-поля заказа (phone, client_name, district_id, entrance, floor) не «нормализовывать» — дублирование намеренное.
- UI, данные и сообщения бота — на русском. Валюта RUB, суммы `DECIMAL(10,2)`. Таймзона `Europe/Moscow`.
- Секреты только в `.env`; в репозитории — `.env.example`.
- Не имитировать готовность: нереализованное помечать TODO с готовыми интерфейсами.
- Коммит после каждого завершённого шага из раздела 17 SPEC.md.

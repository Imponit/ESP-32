# ASSUMPTIONS — принятые решения по неясным местам спецификации

Каждое решение можно пересмотреть; блокирующих архитектуру вопросов не выявлено
(стек, модель данных и машина состояний зафиксированы в SPEC.md).

## Статусы и переходы

1. **Начальный статус заказа при ручном вводе — `new`** (не `draft`).
   `draft` зарезервирован под черновики из входящих каналов (MVP-3) и доступен
   в машине состояний (`draft → new`).
2. **`cancelled`** разрешён из статусов: `draft, new, needs_review, planned,
   assigned, sent_to_driver, accepted_by_driver, in_progress, postponed` —
   т.е. «из любого статуса до `completed`». Из терминальных
   (`completed, failed, refused, cancelled`) отмена невозможна.
3. **`POST /orders/{id}/assign-driver`**: если заказ в `new`, выполняются два
   перехода `new → planned → assigned` (оба пишутся в `order_events`,
   actor = dispatcher). Если в `planned` — один переход. Снятие назначения —
   тем же эндпоинтом с `driver_id: null` (`assigned → planned`).
4. **`postponed → new`**: диспетчер ставит новую дату через `PATCH /orders/{id}`
   и переводит заказ в `new` через `/transition`. Автоматического переноса даты нет.
5. Кнопки пакета в боте двигают и пакет, и его заказы:
   «Принял» — пакет `sent → accepted`, заказы `sent_to_driver → accepted_by_driver`;
   «Начал маршрут» — пакет `accepted → started`, заказы → `in_progress`,
   водитель `work_status = on_route`;
   «Завершил маршрут» — пакет `started → finished`, водитель `work_status = idle`
   (статусы заказов не трогаются — они уже терминальные или останутся висеть
   как проблемные в сводке дня).

## Данные

6. **`day_part` пакета** использует значения `any | first_half | second_half`
   (совместимо с `time_window_type` заказа, без `exact`).
7. **Снапшот district**: `orders.district_id` копируется из адреса при создании
   заказа; при смене адреса заказа (PATCH с новым `address_id`) снапшот-поля
   перекопируются с нового адреса/клиента.
8. **`payment_status`**: `paid`, если `paid_amount >= total_amount`; `partial`,
   если `0 < paid_amount < total_amount`; иначе `unpaid`. Метод платежа из бота
   «Карта-перевод» пишется как `cashless`, «Без оплаты» — платёж не создаётся.
9. **Удаления нет нигде** (заказы/клиенты/адреса) — только деактивация или
   `cancelled`. Историчность важнее.
10. Телефоны храним строкой как ввели; поиск по клиентам — подстрока по имени
    и нормализованному номеру (только цифры). Жёсткой валидации формата нет (MVP-2 — дедупликация).

## Авторизация

11. JWT — HS256, секрет `JWT_SECRET` из `.env`, срок жизни 12 часов
    (рабочая смена диспетчера). Refresh-токенов в MVP-1 нет.
12. Пароли — **bcrypt** (библиотека `bcrypt`, без passlib — passlib не
    поддерживается и конфликтует с новыми версиями bcrypt).
13. Создание пользователей — только seed/админ (эндпоинт `POST /users` не в
    спецификации — отложен; пользователи создаются seed-скриптом). TODO MVP-2.

## Ссылки Яндекс.Карт

14. Точка с координатами: `https://yandex.ru/maps/?pt={lon},{lat}&z=17&l=map`;
    без координат: `https://yandex.ru/maps/?text={адрес urlencoded}`.
15. Маршрут: `https://yandex.ru/maps/?rtext={lat},{lon}~...&rtt=auto`
    (порядок точек = `route_position`, заданный диспетчером). Точки без
    координат в маршрутную ссылку не попадают; если таких точек нет вообще —
    `route_url = null`, у каждого заказа остаётся своя ссылка по тексту адреса.

## Бот и фоновые задачи

16. В dry-run бот-сервис стартует, пишет в лог `DRY RUN: polling отключён` и
    просто живёт (healthcheck-цикл); реальный polling включается только при
    наличии токена и `TELEGRAM_DRY_RUN=0`.
17. Отправка пакета из backend идёт через интерфейс `TelegramClient`;
    реализации: `DryRunTelegramClient` (лог), `AiogramTelegramClient` (реальная),
    `MockTelegramClient` (тесты, копит сообщения в списке).
18. `TaskRunner`: интерфейс с реализацией `BackgroundTasksRunner` поверх
    FastAPI `BackgroundTasks`. Отправка в Telegram выполняется фоном.

## Инфраструктура

19. Python-код совместим с 3.11+ (в Docker-образе — 3.12, как в SPEC;
    в среде разработки доступен 3.11 — синтаксис 3.12-only не используется).
20. Тесты: unit-тесты домена — без БД; тесты сервисов/API — SQLite
    (aiosqlite) in-memory, продакшен — только PostgreSQL (asyncpg).
21. Seed-учётки (только для разработки): `admin / admin123`,
    `dispatcher / dispatcher123`.
22. Настройка `timezone` и `max_route_points` читаются из таблицы `settings`
    с дефолтами `Europe/Moscow` и `9`.
23. Frontend в dev-режиме ходит в backend через Vite proxy (`/api`); в
    docker compose — nginx раздаёт статику и проксирует `/api` на backend.

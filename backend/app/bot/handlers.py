"""Хэндлеры бота водителя. Вся доменная логика — через service layer
(та же машина состояний, те же order_events)."""

from datetime import date
from decimal import Decimal, InvalidOperation

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.bot.keyboards import batch_keyboard, contact_keyboard, order_keyboard, payment_keyboard
from app.core.enums import BatchStatus, OrderStatus, PaymentMethod
from app.core.state_machine import TransitionError
from app.db import SessionLocal
from app.models import Order, OrderEvent, RouteBatch
from app.services import driver_actions
from app.services.dispatch import build_batch_message
from app.services.errors import NotFoundError, ValidationError

router = Router()

ACTIVE_ORDER_STATUSES = (
    OrderStatus.sent_to_driver,
    OrderStatus.accepted_by_driver,
    OrderStatus.in_progress,
)


class PaymentForm(StatesGroup):
    amount = State()


class ReasonForm(StatesGroup):
    reason = State()  # для fail/refuse


class CommentForm(StatesGroup):
    text = State()


async def _require_driver(session, message_or_cb) -> object | None:
    driver = await driver_actions.driver_by_telegram(session, message_or_cb.from_user.id)
    if driver is None:
        target = (
            message_or_cb.message if isinstance(message_or_cb, CallbackQuery) else message_or_cb
        )
        await target.answer("Вы не зарегистрированы. Отправьте /start и поделитесь контактом.")
    return driver


@router.message(CommandStart())
async def cmd_start(message: Message):
    async with SessionLocal() as session:
        driver = await driver_actions.driver_by_telegram(session, message.from_user.id)
    if driver is not None:
        await message.answer(f"Вы уже зарегистрированы, {driver.name}. Команды: /today /status")
        return
    await message.answer(
        "Здравствуйте! Это бот водителя доставки воды.\n"
        "Поделитесь контактом, чтобы я нашёл вас в базе.",
        reply_markup=contact_keyboard(),
    )


@router.message(F.contact)
async def on_contact(message: Message):
    if message.contact.user_id != message.from_user.id:
        await message.answer("Пожалуйста, отправьте свой собственный контакт.")
        return
    async with SessionLocal() as session:
        driver = await driver_actions.register_driver_telegram(
            session, message.contact.phone_number, message.from_user.id
        )
        await session.commit()
    if driver is None:
        await message.answer(
            "Не нашёл вас в базе по этому номеру. Обратитесь к диспетчеру — "
            "он привяжет ваш Telegram вручную.",
            reply_markup=ReplyKeyboardRemove(),
        )
    else:
        await message.answer(
            f"Готово, {driver.name}! Вы привязаны. Команды: /today /status",
            reply_markup=ReplyKeyboardRemove(),
        )


@router.message(Command("today"))
async def cmd_today(message: Message):
    """Задания на сегодня: пакеты водителя с заказами и кнопками."""
    async with SessionLocal() as session:
        driver = await _require_driver(session, message)
        if driver is None:
            return
        batches = (
            (
                await session.execute(
                    select(RouteBatch)
                    .where(
                        RouteBatch.driver_id == driver.id,
                        RouteBatch.delivery_date == date.today(),
                        RouteBatch.status != BatchStatus.draft,
                    )
                    .options(selectinload(RouteBatch.district))
                )
            )
            .scalars()
            .all()
        )
        if not batches:
            await message.answer("На сегодня заданий нет.")
            return
        for batch in batches:
            orders = (
                (
                    await session.execute(
                        select(Order)
                        .where(Order.route_batch_id == batch.id)
                        .order_by(Order.route_position)
                        .options(selectinload(Order.address))
                    )
                )
                .scalars()
                .all()
            )
            await message.answer(
                build_batch_message(batch, list(orders)), reply_markup=batch_keyboard(batch)
            )
            for o in orders:
                if o.status in ACTIVE_ORDER_STATUSES:
                    await message.answer(
                        f"Заказ №{o.id}: {o.address_text} — {o.status.value}",
                        reply_markup=order_keyboard(o),
                    )


@router.message(Command("status"))
async def cmd_status(message: Message):
    """Текущий статус и остаток заказов."""
    async with SessionLocal() as session:
        driver = await _require_driver(session, message)
        if driver is None:
            return
        remaining = (
            (
                await session.execute(
                    select(Order).where(
                        Order.assigned_driver_id == driver.id,
                        Order.delivery_date == date.today(),
                        Order.status.in_(ACTIVE_ORDER_STATUSES),
                    )
                )
            )
            .scalars()
            .all()
        )
    status_ru = "на маршруте" if driver.work_status.value == "on_route" else "свободен"
    lines = [f"Статус: {status_ru}. Осталось заказов: {len(remaining)}"]
    lines += [f"• №{o.id} {o.address_text}" for o in remaining]
    await message.answer("\n".join(lines))


@router.callback_query(F.data.startswith("batch:"))
async def on_batch_action(cb: CallbackQuery):
    _, action, batch_id = cb.data.split(":")
    async with SessionLocal() as session:
        driver = await _require_driver(session, cb)
        if driver is None:
            await cb.answer()
            return
        batch = await session.get(RouteBatch, int(batch_id))
        if batch is None or batch.driver_id != driver.id:
            await cb.answer("Пакет не найден", show_alert=True)
            return
        try:
            if action == "accept":
                await driver_actions.batch_accept(session, batch, driver)
                text = "Пакет принят. Жмите «Начал маршрут», когда выезжаете."
            elif action == "start":
                await driver_actions.batch_start(session, batch, driver)
                text = "Маршрут начат. Удачной дороги!"
            else:
                await driver_actions.batch_finish(session, batch, driver)
                text = "Маршрут завершён. Спасибо!"
            await session.commit()
        except (ValidationError, TransitionError) as e:
            await cb.answer(str(e), show_alert=True)
            return
    await cb.message.answer(text)
    await cb.answer()


@router.callback_query(F.data.startswith("order:"))
async def on_order_action(cb: CallbackQuery, state: FSMContext):
    _, action, order_id = cb.data.split(":")
    async with SessionLocal() as session:
        driver = await _require_driver(session, cb)
        if driver is None:
            await cb.answer()
            return
        try:
            order = await driver_actions.driver_order(session, driver, int(order_id))
        except NotFoundError as e:
            await cb.answer(str(e), show_alert=True)
            return

        if action == "phone":
            await cb.answer(f"Телефон клиента: {order.phone}", show_alert=True)
            return
        if action == "done":
            await cb.message.answer(
                f"Заказ №{order.id}. Как оплатили? Сумма по умолчанию {order.total_amount} ₽.",
                reply_markup=payment_keyboard(order),
            )
            await cb.answer()
            return
        if action in ("fail", "refuse"):
            await state.set_state(ReasonForm.reason)
            await state.update_data(order_id=order.id, kind=action)
            await cb.message.answer("Напишите короткую причину одним сообщением:")
            await cb.answer()
            return
        if action == "comment":
            await state.set_state(CommentForm.text)
            await state.update_data(order_id=order.id)
            await cb.message.answer("Напишите комментарий к заказу:")
            await cb.answer()
            return
        if action == "postpone":
            try:
                await driver_actions.order_postpone(session, driver, order)
                await session.commit()
            except (ValidationError, TransitionError) as e:
                await cb.answer(str(e), show_alert=True)
                return
            await cb.message.answer(
                f"Заказ №{order.id} перенесён. Новую дату поставит диспетчер."
            )
            await cb.answer()


@router.callback_query(F.data.startswith("pay:"))
async def on_payment_method(cb: CallbackQuery, state: FSMContext):
    _, method, order_id = cb.data.split(":")
    async with SessionLocal() as session:
        driver = await _require_driver(session, cb)
        if driver is None:
            await cb.answer()
            return
        try:
            order = await driver_actions.driver_order(session, driver, int(order_id))
            if method == "none":
                await driver_actions.order_complete(session, driver, order, None, None)
                await session.commit()
                await cb.message.answer(f"Заказ №{order.id} выполнен, без оплаты.")
                await cb.answer()
                return
        except (NotFoundError, ValidationError, TransitionError) as e:
            await cb.answer(str(e), show_alert=True)
            return
    await state.set_state(PaymentForm.amount)
    await state.update_data(order_id=int(order_id), method=method)
    await cb.message.answer(
        f"Введите сумму (Enter по умолчанию {order.total_amount} ₽) "
        f"или отправьте «ок» для суммы по умолчанию:"
    )
    await cb.answer()


@router.message(PaymentForm.amount)
async def on_payment_amount(message: Message, state: FSMContext):
    data = await state.get_data()
    raw = (message.text or "").strip().replace(",", ".")
    async with SessionLocal() as session:
        driver = await _require_driver(session, message)
        if driver is None:
            return
        try:
            order = await driver_actions.driver_order(session, driver, data["order_id"])
            if raw.lower() in ("ок", "ok", ""):
                amount = None  # сумма по умолчанию = total_amount
            else:
                try:
                    amount = Decimal(raw)
                except InvalidOperation:
                    await message.answer("Не понял сумму. Введите число, например 600:")
                    return
            method = PaymentMethod.cash if data["method"] == "cash" else PaymentMethod.cashless
            order = await driver_actions.order_complete(session, driver, order, method, amount)
            await session.commit()
        except (NotFoundError, ValidationError, TransitionError) as e:
            await message.answer(str(e))
            await state.clear()
            return
    await state.clear()
    await message.answer(
        f"Заказ №{order.id} выполнен. Оплата {order.paid_amount} ₽ зафиксирована."
    )


@router.message(ReasonForm.reason)
async def on_reason(message: Message, state: FSMContext):
    data = await state.get_data()
    reason = (message.text or "").strip()
    if not reason:
        await message.answer("Причина не может быть пустой. Напишите текст:")
        return
    async with SessionLocal() as session:
        driver = await _require_driver(session, message)
        if driver is None:
            return
        try:
            order = await driver_actions.driver_order(session, driver, data["order_id"])
            if data["kind"] == "fail":
                await driver_actions.order_fail(session, driver, order, reason)
            else:
                await driver_actions.order_refuse(session, driver, order, reason)
            await session.commit()
        except (NotFoundError, ValidationError, TransitionError) as e:
            await message.answer(str(e))
            await state.clear()
            return
    await state.clear()
    kind_ru = "ошибка" if data["kind"] == "fail" else "отказ"
    await message.answer(f"Заказ №{data['order_id']}: {kind_ru} зафиксирована, причина записана.")


@router.message(CommentForm.text)
async def on_comment(message: Message, state: FSMContext):
    data = await state.get_data()
    async with SessionLocal() as session:
        driver = await _require_driver(session, message)
        if driver is None:
            return
        try:
            order = await driver_actions.driver_order(session, driver, data["order_id"])
        except NotFoundError as e:
            await message.answer(str(e))
            await state.clear()
            return
        session.add(
            OrderEvent(
                order_id=order.id,
                event_type="comment",
                actor_type="driver",
                actor_id=driver.id,
                comment=(message.text or "").strip(),
            )
        )
        await session.commit()
    await state.clear()
    await message.answer("Комментарий записан.")

# TODO (опционально): приём геолокации водителя

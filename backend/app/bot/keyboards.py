"""Клавиатуры бота. Callback-данные: '<сущность>:<действие>:<id>'."""

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from app.models import Order, RouteBatch


def contact_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Поделиться контактом", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def batch_keyboard(batch: RouteBatch) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Принял", callback_data=f"batch:accept:{batch.id}"),
                InlineKeyboardButton(
                    text="🚚 Начал маршрут", callback_data=f"batch:start:{batch.id}"
                ),
                InlineKeyboardButton(
                    text="🏁 Завершил маршрут", callback_data=f"batch:finish:{batch.id}"
                ),
            ]
        ]
    )


def order_keyboard(order: Order) -> InlineKeyboardMarkup:
    oid = order.id
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Выполнен", callback_data=f"order:done:{oid}"),
                InlineKeyboardButton(text="⚠️ Ошибка", callback_data=f"order:fail:{oid}"),
            ],
            [
                InlineKeyboardButton(text="🚫 Отказались", callback_data=f"order:refuse:{oid}"),
                InlineKeyboardButton(text="📅 Перенос", callback_data=f"order:postpone:{oid}"),
            ],
            [
                InlineKeyboardButton(text="💬 Комментарий", callback_data=f"order:comment:{oid}"),
                InlineKeyboardButton(
                    text="📞 Показать телефон", callback_data=f"order:phone:{oid}"
                ),
            ],
        ]
    )


def payment_keyboard(order: Order) -> InlineKeyboardMarkup:
    oid = order.id
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="💵 Наличные", callback_data=f"pay:cash:{oid}"),
                InlineKeyboardButton(text="💳 Карта-перевод", callback_data=f"pay:cashless:{oid}"),
                InlineKeyboardButton(text="❌ Без оплаты", callback_data=f"pay:none:{oid}"),
            ]
        ]
    )

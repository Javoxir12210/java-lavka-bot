# -*- coding: utf-8 -*-
from enum import Enum
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler
)
import re
import logging

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# === НАСТРОЙКИ (ЗАМЕНИТЬ НА СВОИ!) ===
BOT_TOKEN = "8398708431:AAHgw4d9FxGD7dqc1RHsKDMaHBTQpo6ryuw"  # ⚠️ Убедитесь: НЕТ ПРОБЕЛОВ!
CHAT_ID = 5616310180  # ID чата, куда приходят заказы

# === СОСТОЯНИЯ РАЗГОВОРА ===
class States(Enum):
    NAME = 0
    DISTRICT = 1
    PHONE = 2
    ITEMS = 3
    DELIVERY = 4
    CONFIRM = 5

# === ДАННЫЕ ДЛЯ КЛАВИАТУР ===
DISTRICTS = ["Центр", "Север", "Юг", "Запад", "Восток"]
DELIVERY_TYPES = ["🚗 Доставка", "🏃‍♂️ Самовывоз"]


def create_keyboard(buttons: list, columns: int = 2) -> ReplyKeyboardMarkup:
    """
    Создаёт клавиатуру с заданным количеством кнопок в строке.
    Гарантирует, что результат — список списков.
    """
    keyboard = []
    for i in range(0, len(buttons), columns):
        row = [KeyboardButton(text=item) for item in buttons[i:i + columns]]
        keyboard.append(row)
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начало диалога — запрос имени"""
    await update.message.reply_text(
        "✨ Добро пожаловать в <b>Java Lavka</b>! ✨\n\n"
        "Пожалуйста, укажите ваше имя:",
        reply_markup=ReplyKeyboardMarkup([["/cancel"]], resize_keyboard=True),
        parse_mode='HTML'
    )
    return States.NAME.value


async def process_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохранение имени и запрос района или геолокации"""
    context.user_data['name'] = update.message.text.strip()

    # Кнопка геолокации
    location_btn = KeyboardButton("📍 Отправить геолокацию", request_location=True)
    district_kb = create_keyboard(DISTRICTS)

    # Исправление ошибки: преобразуем .keyboard в список списков
    try:
        keyboard_rows = [list(row) for row in district_kb.keyboard]
    except TypeError:
        keyboard_rows = district_kb.keyboard  # если и так list

    # Добавляем кнопку геолокации сверху
    full_keyboard = [[location_btn]] + keyboard_rows
    reply_markup = ReplyKeyboardMarkup(full_keyboard, resize_keyboard=True, one_time_keyboard=True)

    await update.message.reply_text(
        "📍 Выберите район ниже или отправьте свою геолокацию:",
        reply_markup=reply_markup
    )
    return States.DISTRICT.value


async def process_district(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка района или геолокации"""
    if update.message.location:
        loc = update.message.location
        context.user_data['location'] = f"{loc.latitude:.6f},{loc.longitude:.6f}"
        context.user_data['district'] = "📍 По геолокации"
        logger.info(f"Получена геолокация: {context.user_data['location']}")
    else:
        context.user_data['district'] = update.message.text.strip()

    # Кнопка отправки номера
    phone_btn = KeyboardButton("📞 Отправить номер", request_contact=True)
    reply_markup = ReplyKeyboardMarkup(
        [[phone_btn], ["/cancel"]],
        resize_keyboard=True,
        one_time_keyboard=True
    )

    await update.message.reply_text(
        "📞 Укажите номер телефона в формате:\n"
        "<code>+79991234567</code> или <code>89991234567</code>",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )
    return States.PHONE.value


async def process_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получение и валидация номера телефона"""
    if update.message.contact:
        phone = update.message.contact.phone_number
    else:
        phone = update.message.text.strip()
        if not re.match(r'^(\+7|8)\d{10}$', phone):
            await update.message.reply_text(
                "❌ Неверный формат номера!\n"
                "Пример: <code>+79991234567</code>",
                parse_mode='HTML'
            )
            return States.PHONE.value

    # Приведение к формату +7
    phone = re.sub(r'^8', '+7', phone)
    context.user_data['phone'] = phone

    await update.message.reply_text(
        "🛒 Перечислите товары, которые хотите заказать (через запятую):",
        reply_markup=ReplyKeyboardMarkup([["/cancel"]], resize_keyboard=True)
    )
    return States.ITEMS.value


async def process_items(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохранение списка товаров"""
    context.user_data['items'] = update.message.text.strip()

    await update.message.reply_text(
        "🚚 Выберите удобный способ получения:",
        reply_markup=create_keyboard(DELIVERY_TYPES)
    )
    return States.DELIVERY.value


async def process_delivery(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохранение способа доставки и показ заказа для подтверждения"""
    context.user_data['delivery'] = update.message.text.strip()

    order_text = (
        "🛒 <b>Ваш заказ</b>:\n\n"
        f"👤 <b>Имя</b>: {context.user_data['name']}\n"
        f"📍 <b>Район</b>: {context.user_data['district']}\n"
        f"📞 <b>Телефон</b>: {context.user_data['phone']}\n"
        f"📦 <b>Товары</b>: {context.user_data['items']}\n"
        f"🚚 <b>Способ</b>: {context.user_data['delivery']}"
    )

    # Кнопки подтверждения
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_yes"),
            InlineKeyboardButton("🔄 Изменить", callback_data="confirm_edit")
        ],
        [
            InlineKeyboardButton("❌ Отменить", callback_data="confirm_no")
        ]
    ])

    await update.message.reply_text(
        order_text,
        reply_markup=keyboard,
        parse_mode='HTML'
    )
    return States.CONFIRM.value


async def confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка подтверждения заказа"""
    query = update.callback_query
    await query.answer()

    if query.data == "confirm_yes":
        # Формируем сообщение для администратора
        admin_msg = (
            "🚀 <b>НОВЫЙ ЗАКАЗ</b>!\n\n"
            f"👤 <b>Имя</b>: {context.user_data['name']}\n"
            f"📞 <b>Телефон</b>: {context.user_data['phone']}\n"
            f"📦 <b>Товары</b>: {context.user_data['items']}\n"
            f"🚚 <b>Способ</b>: {context.user_data['delivery']}"
        )
        if 'location' in context.user_data:
            admin_msg += f"\n📍 <b>Координаты</b>: {context.user_data['location']}"

        try:
            await context.bot.send_message(
                chat_id=CHAT_ID,
                text=admin_msg,
                parse_mode='HTML'
            )
            await query.edit_message_text(
                "🎉 <b>Заказ принят!</b>\n\n"
                "Спасибо! Наш менеджер свяжется с вами в ближайшее время.",
                parse_mode='HTML'
            )
            logger.info("Заказ успешно отправлен в чат")
        except Exception as e:
            logger.error(f"Ошибка отправки заказа: {e}")
            await query.edit_message_text(
                "⚠️ Произошла ошибка при отправке заказа. Попробуйте позже."
            )

    elif query.data == "confirm_edit":
        await query.edit_message_text("🔄 Для изменения заказа начните сначала: /start")

    else:  # confirm_no
        await query.edit_message_text("❌ Заказ отменён. Чтобы начать заново — /start")

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отмена текущего заказа"""
    await update.message.reply_text(
        "❌ Заказ отменён.\n\n"
        "Чтобы оформить новый — введите /start",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END


def main() -> None:
    """Запуск бота"""
    try:
        application = ApplicationBuilder().token(BOT_TOKEN).build()

        # Обработчик диалога
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler('start', start)],
            states={
                States.NAME.value: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, process_name)
                ],
                States.DISTRICT.value: [
                    MessageHandler(filters.TEXT | filters.LOCATION, process_district)
                ],
                States.PHONE.value: [
                    MessageHandler(filters.TEXT | filters.CONTACT, process_phone)
                ],
                States.ITEMS.value: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, process_items)
                ],
                States.DELIVERY.value: [
                    MessageHandler(
                        filters.Regex(f"^({'|'.join(map(re.escape, DELIVERY_TYPES))})$"),
                        process_delivery
                    )
                ],
                States.CONFIRM.value: [
                    CallbackQueryHandler(confirm_order)
                ],
            },
            fallbacks=[
                CommandHandler('cancel', cancel),
                MessageHandler(filters.Regex("^/cancel$"), cancel)
            ],
            per_message=False,
            allow_reentry=True
        )

        application.add_handler(conv_handler)
        application.add_handler(CommandHandler('cancel', cancel))

        logger.info("✅ Бот запущен и готов к работе")
        application.run_polling(drop_pending_updates=True)

    except Exception as e:
        logger.critical(f"❌ Ошибка запуска бота: {e}")


if __name__ == '__main__':
    main()
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from utils.database import (get_courier, add_courier, get_active_orders,
                             get_order_by_id, take_order, complete_delivery,
                             get_courier_history, update_order_status,
                             format_order_number, add_pending_update)

router = Router()


class RegState(StatesGroup):
    waiting_name  = State()
    waiting_phone = State()


class DeliveryAction(CallbackData, prefix="del"):
    action: str
    order_id: int


class PaymentAction(CallbackData, prefix="pay"):
    method: str
    order_id: int


def main_keyboard():
    builder = ReplyKeyboardBuilder()
    builder.button(text="📦 Активные заказы")
    builder.button(text="📋 История доставок")
    builder.adjust(2)
    return builder.as_markup(resize_keyboard=True)


@router.message(Command("start"))
async def start(message: types.Message, state: FSMContext):
    await state.clear()
    courier = get_courier(message.from_user.id)

    if courier:
        if courier["status"] == "pending":
            await message.answer("⏳ Ваша заявка на рассмотрении. Ожидайте одобрения администратора.")
        elif courier["status"] == "active":
            await message.answer(
                f"👋 Добро пожаловать, {courier['name']}!",
                reply_markup=main_keyboard()
            )
        elif courier["status"] == "blocked":
            await message.answer("🚫 Ваш аккаунт заблокирован. Обратитесь к администратору.")
        return

    await message.answer(
        "👋 Добро пожаловать в систему доставки <b>ХАНТ ХАУС</b>!\n\n"
        "Для регистрации введите ваше имя:"
    )
    await state.set_state(RegState.waiting_name)


@router.message(RegState.waiting_name)
async def reg_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    builder = ReplyKeyboardBuilder()
    builder.button(text="📱 Отправить номер", request_contact=True)
    await message.answer(
        "Отправьте ваш номер телефона:",
        reply_markup=builder.as_markup(resize_keyboard=True)
    )
    await state.set_state(RegState.waiting_phone)


@router.message(RegState.waiting_phone, F.content_type.in_({"contact", "text"}))
async def reg_phone(message: types.Message, state: FSMContext):
    from config import CAFE_ADMIN_IDS
    phone = message.contact.phone_number if message.contact else message.text
    data = await state.get_data()
    name = data["name"]

    add_courier(message.from_user.id, name, phone)

    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Одобрить",
              callback_data=f"approve_{message.from_user.id}")
    kb.button(text="❌ Отклонить",
              callback_data=f"reject_{message.from_user.id}")
    kb.adjust(2)

    for admin_id in CAFE_ADMIN_IDS:
        try:
            await message.bot.send_message(
                admin_id,
                f"🆕 <b>Новый курьер хочет зарегистрироваться</b>\n\n"
                f"👤 Имя: {name}\n"
                f"📞 Телефон: {phone}\n"
                f"🆔 ID: {message.from_user.id}",
                reply_markup=kb.as_markup()
            )
        except Exception:
            pass

    await message.answer(
        "✅ Заявка отправлена! Ожидайте одобрения администратора.",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await state.clear()


@router.message(F.text == "📦 Активные заказы")
async def active_orders(message: types.Message):
    courier = get_courier(message.from_user.id)
    if not courier or courier["status"] != "active":
        await message.answer("🚫 Доступ запрещён.")
        return

    orders = get_active_orders()
    if not orders:
        await message.answer("📭 Активных заказов нет.")
        return

    for row in orders:
        order_num = format_order_number(row["id"], row["daily_number"], row["order_date"])
        details_lines = row["details"].split("\n")
        items_text = "\n".join(
            line for line in details_lines if line.startswith("•")
        )
        total = row["details"].split("ИТОГО:")[-1].strip() if "ИТОГО:" in row["details"] else ""

        kb = InlineKeyboardBuilder()
        kb.button(text="🚀 Взять заказ",
                  callback_data=DeliveryAction(action="take", order_id=row["id"]).pack())

        await message.answer(
            f"📦 <b>Заказ {order_num}</b>\n"
            f"━━━━━━━━━━━━━━━\n"
            f"{items_text}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"💰 Итого: {total}\n"
            f"🏘 Нас. пункт: {row['city'] or '—'}\n"
            f"🏠 Адрес: {row['address']}\n"
            f"📞 Телефон: {row['phone']}\n"
            f"💳 Оплата: {row['payment'] or row['method']}",
            reply_markup=kb.as_markup()
        )


@router.callback_query(DeliveryAction.filter(F.action == "take"))
async def take_order_handler(callback: types.CallbackQuery, callback_data: DeliveryAction):
    from config import CAFE_ADMIN_IDS
    courier = get_courier(callback.from_user.id)
    if not courier or courier["status"] != "active":
        await callback.answer("🚫 Доступ запрещён.", show_alert=True)
        return

    order_id = callback_data.order_id
    success = take_order(order_id, courier["id"])

    if not success:
        await callback.answer("❌ Заказ уже взят другим курьером!", show_alert=True)
        return

    await callback.answer()

    order = get_order_by_id(order_id)
    order_num = format_order_number(order_id, order["daily_number"], order["order_date"])

    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Доставлено",
              callback_data=DeliveryAction(action="done", order_id=order_id).pack())

    await callback.message.edit_text(
        f"{callback.message.text}\n\n🚀 Вы взяли этот заказ!",
        reply_markup=kb.as_markup()
    )

    for admin_id in CAFE_ADMIN_IDS:
        try:
            await callback.bot.send_message(
                admin_id,
                f"🚀 Курьер <b>{courier['name']}</b> взял заказ {order_num}"
            )
        except Exception:
            pass


@router.callback_query(DeliveryAction.filter(F.action == "done"))
async def done_handler(callback: types.CallbackQuery, callback_data: DeliveryAction):
    await callback.answer()
    order_id = callback_data.order_id
    courier = get_courier(callback.from_user.id)

    # Уведомляем клиента что курьер прибыл — через бот кафе
    add_pending_update(
        order_id,
        courier["name"],
        callback.from_user.id,
        "",
        update_type="arrived"
    )

    kb = InlineKeyboardBuilder()
    kb.button(text="💵 Наличными",
              callback_data=PaymentAction(method="Наличными", order_id=order_id).pack())
    kb.button(text="💳 Картой",
              callback_data=PaymentAction(method="Картой", order_id=order_id).pack())
    kb.button(text="📱 QR/СБП",
              callback_data=PaymentAction(method="QR/СБП", order_id=order_id).pack())
    kb.adjust(1)

    await callback.message.edit_text(
        f"{callback.message.text}\n\n💳 Подтвердите способ оплаты:",
        reply_markup=kb.as_markup()
    )


@router.callback_query(PaymentAction.filter())
async def payment_handler(callback: types.CallbackQuery, callback_data: PaymentAction):
    await callback.answer()

    order_id = callback_data.order_id
    payment = callback_data.method
    courier = get_courier(callback.from_user.id)

    complete_delivery(order_id, payment)
    update_order_status(order_id, "Доставлен")

    add_pending_update(
        order_id,
        courier["name"],
        callback.from_user.id,
        payment,
        update_type="delivered"
    )

    await callback.message.edit_text(
        f"{callback.message.text}\n\n🏁 Оплата подтверждена: {payment}"
    )


@router.message(F.text == "📋 История доставок")
async def history(message: types.Message):
    courier = get_courier(message.from_user.id)
    if not courier or courier["status"] != "active":
        await message.answer("🚫 Доступ запрещён.")
        return

    deliveries = get_courier_history(courier["id"])
    if not deliveries:
        await message.answer("📭 История доставок пуста.")
        return

    text = "📋 <b>Ваши последние доставки:</b>\n\n"
    for d in deliveries:
        order_num = format_order_number(d["order_id"], d["daily_number"], d["order_date"])
        text += (
            f"📦 Заказ {order_num}\n"
            f"🏠 {d['address']}\n"
            f"💳 Оплата: {d['payment_method']}\n"
            f"🕐 {d['delivered_at']}\n"
            f"━━━━━━━━━━━━\n"
        )
    await message.answer(text)

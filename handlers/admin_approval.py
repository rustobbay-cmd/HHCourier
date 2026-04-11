from aiogram import Router, F, types
from config import CAFE_ADMIN_IDS
from utils.database import update_courier_status, get_courier

router = Router()


@router.callback_query(F.data.startswith("approve_"))
async def approve_courier(callback: types.CallbackQuery):
    if callback.from_user.id not in CAFE_ADMIN_IDS:
        await callback.answer("🚫 Нет доступа.", show_alert=True)
        return

    await callback.answer()
    courier_user_id = int(callback.data.split("_")[1])
    update_courier_status(courier_user_id, "active")

    courier = get_courier(courier_user_id)

    try:
        await callback.bot.send_message(
            courier_user_id,
            "✅ Ваша заявка одобрена! Добро пожаловать в команду курьеров ХАНТ ХАУС 🛵\n\n"
            "Нажмите /start чтобы начать работу."
        )
    except Exception:
        pass

    await callback.message.edit_text(
        f"{callback.message.text}\n\n✅ Одобрен администратором {callback.from_user.full_name}"
    )


@router.callback_query(F.data.startswith("reject_"))
async def reject_courier(callback: types.CallbackQuery):
    if callback.from_user.id not in CAFE_ADMIN_IDS:
        await callback.answer("🚫 Нет доступа.", show_alert=True)
        return

    await callback.answer()
    courier_user_id = int(callback.data.split("_")[1])
    update_courier_status(courier_user_id, "blocked")

    try:
        await callback.bot.send_message(
            courier_user_id,
            "❌ Ваша заявка отклонена. Обратитесь к администратору."
        )
    except Exception:
        pass

    await callback.message.edit_text(
        f"{callback.message.text}\n\n❌ Отклонён администратором {callback.from_user.full_name}"
    )

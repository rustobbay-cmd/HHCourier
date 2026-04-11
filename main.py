import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from config import COURIER_BOT_TOKEN
from utils.database import init_courier_tables, get_active_couriers
from utils.database import get_my_notifications, mark_my_notification_processed
from handlers import courier, admin_approval


async def check_courier_notifications(bot):
    while True:
        try:
            couriers = get_active_couriers()
            for c in couriers:
                notifications = get_my_notifications(c["user_id"])
                for notif in notifications:
                    try:
                        await bot.send_message(
                            c["user_id"],
                            notif["message"]
                        )
                        mark_my_notification_processed(notif["id"])
                    except Exception:
                        pass
        except Exception:
            pass
        await asyncio.sleep(3)


async def main():
    logging.basicConfig(level=logging.INFO)

    bot = Bot(
        token=COURIER_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()

    dp.include_router(admin_approval.router)
    dp.include_router(courier.router)

    init_courier_tables()

    await bot.delete_webhook(drop_pending_updates=True)
    print("🚀 Бот курьеров запущен!")

    asyncio.create_task(check_courier_notifications(bot))

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())

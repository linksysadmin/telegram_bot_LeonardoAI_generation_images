import asyncio
import logging
import sys
from logging.handlers import RotatingFileHandler

from aiohttp import web

from aiogram.client.default import DefaultBotProperties
from aiogram.types import BotCommand
from aiogram.fsm.storage.redis import RedisStorage
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from config import TELEGRAM_TOKEN, BASE_WEBHOOK_URL, WEBHOOK_PATH, WEB_SERVER_HOST, WEB_SERVER_PORT, REDIS_URL, DEBUG
from app.middleware.user_middleware import CheckUserInGroupMiddleware
from app.routers import router as main_router
from tasks import launching_the_daily_generation_reset_task

log = logging.getLogger('')
log.setLevel(logging.INFO)

format = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt='%m.%d.%Y| %H:%M:%S')

console_stream = logging.StreamHandler(sys.stdout)
console_stream.setFormatter(format)
log.addHandler(console_stream)

file_stream = RotatingFileHandler('log.log', maxBytes=(1048576*5), backupCount=7)
file_stream.setFormatter(format)
log.addHandler(file_stream)

storage = RedisStorage.from_url(REDIS_URL)
dp = Dispatcher()
# dp.message.outer_middleware.register(CheckUserInGroupMiddleware(storage=storage))
# dp.callback_query.outer_middleware.register(CheckUserInGroupMiddleware(storage=storage))
# dp.chat_member.outer_middleware.register(ChannelHandlerMiddleware(storage=storage))
dp.include_router(main_router)
# dp.message.middleware.register(LogMiddleware())
bot = Bot(token=TELEGRAM_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

COMMANDS = [
    BotCommand(command='start', description='Начать'),
    BotCommand(command='help', description='Помощь'),
    BotCommand(command='buy', description='Купить генерации'),
    BotCommand(command='account', description='Личный кабинет'),
]




async def on_startup(bot: Bot) -> None:
    await bot.set_my_commands(COMMANDS)
    await bot.set_webhook(
        f"{BASE_WEBHOOK_URL}{WEBHOOK_PATH}",
    )
    logging.warning(f'Вебхук задан: {await bot.get_webhook_info()}')


async def on_shutdown(bot):
    await bot.delete_webhook()
    logging.warning(f'Вебхук удален')


def main() -> None:
    # При запуске приложения
    dp.startup.register(on_startup)

    # При закрытии приложения
    dp.shutdown.register(on_shutdown)
    app = web.Application()

    webhook_requests_handler = SimpleRequestHandler(  # TokenBasedRequestHandler
        dispatcher=dp,
        bot=bot,
    )
    webhook_requests_handler.register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    logging.info(f'Приложение запущено')
    web.run_app(app, host=WEB_SERVER_HOST, port=WEB_SERVER_PORT)


async def start_bot_testing_mode() -> None:
    try:
        await bot.set_my_commands(COMMANDS)
        await launching_the_daily_generation_reset_task()
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    if DEBUG:
        asyncio.run(start_bot_testing_mode())
    else:
        try:
            main()
        except Exception as e:
            logging.error(e)

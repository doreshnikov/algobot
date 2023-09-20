from aiogram import Dispatcher

from .handlers import router
from .middleware.enabler import EnablerMiddleware
from .middleware.tg_updater import TelegramUpdaterMiddleware

dispatcher = Dispatcher()
dispatcher.include_router(router)
dispatcher.message.middleware.register(EnablerMiddleware())
dispatcher.update.outer_middleware.register(TelegramUpdaterMiddleware())

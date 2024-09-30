from aiogram import Dispatcher
from aiogram.utils.chat_action import ChatActionMiddleware

from .handlers import router
from .middleware.enabler import EnablerMiddleware
from .middleware.user_data import UserDataMiddleware

dispatcher = Dispatcher()
dispatcher.include_router(router)
dispatcher.message.middleware.register(EnablerMiddleware())
dispatcher.message.middleware.register(ChatActionMiddleware())
dispatcher.update.outer_middleware.register(UserDataMiddleware())
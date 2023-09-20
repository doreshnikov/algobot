from aiogram import Dispatcher

from .handlers import router
from .middleware.enabler import EnablerMiddleware

dispatcher = Dispatcher()
dispatcher.include_router(router)
dispatcher.message.middleware.register(EnablerMiddleware())

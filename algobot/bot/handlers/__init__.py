from aiogram import Router
from aiogram.filters import Command

from .register import register_router
from .toggle import toggle_router
from .special.debug import debug_router
from .special.cancel import cancel_handler

from algobot.config import local_config

router = Router()
router.message.register(cancel_handler, Command('cancel'))
router.include_routers(register_router, toggle_router)

if local_config.get('debug_mode', False):
    router.include_router(debug_router)

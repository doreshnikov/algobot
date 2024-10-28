from aiogram import Router

from algobot.config import local_config
from .register import register_router
from .reload import reload_router
from .special.cancel import cancel_handler
from .special.debug import debug_router
from .tasks import tasks_router
from .toggle import toggle_router

router = Router()
# router.message.register(cancel_handler, Command('cancel'))
router.include_routers(
    register_router,
    toggle_router,
    tasks_router,
    reload_router
)

if local_config.get('debug_mode', False):
    router.include_router(debug_router)

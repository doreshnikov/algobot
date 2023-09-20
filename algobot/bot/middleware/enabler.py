from typing import Callable, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.dispatcher.flags import get_flag
from aiogram.types import Message


class EnablerMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any],
    ):
        is_feature = get_flag(data, 'feature')
        is_enabled = get_flag(data, 'enabled')
        if is_feature and not is_enabled:
            return await event.reply('This feature is disabled')
        return await handler(event, data)

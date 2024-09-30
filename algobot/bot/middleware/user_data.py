from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Update

from algobot.data.connectors.users import Users
from algobot.data.helpers.formatters import full_name


class UserDataMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Update, dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: dict[str, Any],
    ):
        full_data = event.model_dump()[event.event_type]
        user = full_data['from_user']
        tg_id, tg_username = user['id'], user['username']
        tg_name = full_name(user['first_name'], user['last_name'])

        db_user = Users.get_user(tg_id)
        if db_user is not None and (
            db_user['tg_username'] != tg_username or db_user['tg_name'] != tg_name
        ):
            Users.update_tg_data(tg_id, tg_username, tg_name)
        data.update({'user': Users.get_user(tg_id)})

        await handler(event, data)

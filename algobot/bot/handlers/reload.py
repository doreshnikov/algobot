from aiogram import Router
from aiogram.filters.command import Command
from aiogram.types import Message

from ..filters.access import IsTeacher
from ...data.connectors.tables import Table
from ...data.helpers.defaults import get_default_course

reload_router = Router()


@reload_router.message(IsTeacher, Command('reload'))
async def toggle_command_handler(message: Message):
    group = message.text.removeprefix('/reload ')
    course = get_default_course(group)
    table = Table.get_table(course, group_id=group)
    table.reload(True)
    await message.reply('Ok')

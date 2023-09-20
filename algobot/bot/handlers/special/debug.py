from aiogram.types import Message

from io import StringIO
from contextlib import redirect_stdout, redirect_stderr

from ..feature import EnablerRouter
from algobot.bot.filters.access import IsAdmin

debug_router = EnablerRouter('debug', enabled_by_default=True)


@debug_router.entry_point(IsAdmin)
async def debug_handler(message: Message):
    stdout = StringIO()
    command = message.text.removeprefix(f'/{debug_router.feature_name}').strip()
    with redirect_stdout(stdout), redirect_stderr(stdout):
        try:
            exec(command)
        except Exception as e:
            print(e)
    await message.reply(f'Output:\n```\n{stdout.getvalue()}```', parse_mode='Markdown')

from aiogram.fsm.context import FSMContext
from aiogram.types import Message


async def cancel_handler(message: Message, state: FSMContext):
    await state.clear()
    await message.reply('Current action aborted')

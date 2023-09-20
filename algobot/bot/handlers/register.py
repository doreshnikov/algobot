from enum import Enum

from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, InlineKeyboardMarkup, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .feature import EnablerRouter
from algobot.data.connectors.students import Students
from algobot.data.connectors.users import Users
from algobot.data.helpers.formatters import user_reference, full_student_info


class CommandName(Enum):
    REGISTER = 'register'
    FORGET_ME = 'forget'


register_router = EnablerRouter(CommandName.REGISTER.value, enabled_by_default=True)


class RegisterState(StatesGroup):
    Command = State()
    Group = State()
    Name = State()


class GroupCallback(CallbackData, prefix='group'):
    group_id: str


def group_selector(groups: list[str]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for group_id in groups:
        builder.button(text=group_id, callback_data=GroupCallback(group_id=group_id))
    return builder.as_markup()


@register_router.entry_point()
async def register_command_handler(message: Message, state: FSMContext):
    tg_id = message.from_user.id
    tg_username = message.from_user.username
    tg_name = message.from_user.full_name

    if user := Users.get_user(tg_id):
        full_student_name = full_student_info(user['student_name'], user['group_id'])
        await message.reply(
            f'You are already registered as `{full_student_name}`.\n'
            f'Use /{CommandName.FORGET_ME.value} to reset.',
            parse_mode='Markdown',
        )
        return

    tg_ref = user_reference(tg_id, tg_username, tg_name)
    await state.update_data(
        {
            'message': message,
            'tg_id': tg_id,
            'tg_username': tg_username,
            'tg_name': tg_name,
            'tg_ref': tg_ref,
        }
    )
    await state.set_state(RegisterState.Group)
    groups = Students.list_groups()
    await message.reply('Select your group', reply_markup=group_selector(groups))


@register_router.entry_point(command='forget')
async def forget_command_handler(message: Message, state: FSMContext):
    tg_id = message.from_user.id
    if not Users.get_user(tg_id):
        await message.reply(
            f'You are not registered yet... Use /{CommandName.REGISTER.value} to introduce yourself.'
        )
        return

    await state.clear()
    Users.delete_user(tg_id)
    await message.reply('Your registration is revoked')


@register_router.callback_query(RegisterState.Group, GroupCallback.filter())
async def select_group_handler(query: CallbackQuery, state: FSMContext):
    original_message: Message = (await state.get_data())['message']
    group_id = GroupCallback.unpack(query.data).group_id
    await state.update_data({'group_id': group_id})
    await query.answer(f'Selected group {group_id}')
    await state.set_state(RegisterState.Name)
    await original_message.reply(
        'Please write your name (exactly as in corresponding table)'
    )


@register_router.message(RegisterState.Name)
async def input_name_handler(message: Message, state: FSMContext):
    data = await state.get_data()
    tg_id, tg_username, tg_name = data['tg_id'], data['tg_username'], data['tg_name']
    group_id = data['group_id']
    student_name = message.text

    if not Students.get_student_by_name(group_id, student_name):
        await message.reply(
            f'There is no such student in group `{group_id}`.\n'
            f'Choose another one or contact the administrator.',
            parse_mode='Markdown',
        )
        return
    if user := Users.get_user_by_name(group_id, student_name):
        full_student_name = full_student_info(user['student_name'], user['group_id'])
        holder_reference = user_reference(
            user['tg_id'], user['tg_username'], user['tg_name']
        )
        await message.reply(
            f'User `{full_student_name}` is already taken by {holder_reference}.\n'
            f'Choose another one or contact the administrator.',
            parse_mode='Markdown',
        )
        return

    await state.clear()
    Users.insert_user(tg_id, tg_username, tg_name, group_id, student_name)
    await message.reply(f'Ok, registered as `{student_name}`', parse_mode='Markdown')

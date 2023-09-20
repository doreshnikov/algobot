from enum import Enum

import emoji
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from algobot.data.connectors.users import Users
from .feature import EnablerRouter
from .register import CommandName as RegisterCommandNames
from ...data.connectors.tables import MarkingResult, Table
from ...data.helpers.defaults import get_default_course

tasks_router = EnablerRouter('tasks', enabled_by_default=True)


class CommandName(Enum):
    DECLARE = 'declare'
    RECALL = 'recall'


class WeekCallback(CallbackData, prefix='week'):
    week_name: str


class TaskCallback(CallbackData, prefix='task'):
    task_name: str


class CommitCallback(CallbackData, prefix='commit'):
    pass


class TasksState(StatesGroup):
    Command = State()
    Week = State()
    Task = State()


def week_selector(weeks: list[str]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for week in weeks:
        builder.button(text=week, callback_data=WeekCallback(week_name=week))
    return builder.as_markup()


def task_selector(
    week_name: str, tasks: list[str], selection: set[str]
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for task_name in tasks:
        builder.button(
            text=task_name
            if task_name not in selection
            else f'{task_name}{emoji.emojize(":green_circle:")}',
            callback_data=TaskCallback(task_name=task_name),
        )
    rows = int(len(tasks) ** 0.5)
    builder.row(
        InlineKeyboardButton(text='Commit', callback_data=CommitCallback().pack())
    )
    item_count = [len(tasks) // rows for _ in range(rows)]
    if (remainder := len(tasks) % rows) != 0:
        item_count.append(remainder)
    builder.adjust(*item_count)
    return builder.as_markup()


async def process_entry_point(
    message: Message, state: FSMContext, command: CommandName
):
    tg_id = message.from_user.id
    if user := Users.get_user(tg_id):
        group_id, student_name = user['group_id'], user['student_name']
        await state.update_data({'group_id': group_id, 'student_name': student_name})
    else:
        await message.reply(
            f'Please, first use /{RegisterCommandNames.REGISTER.value} to introduce yourself...'
        )
        return

    default_course = get_default_course(group_id)
    table = Table.get_table(default_course, group_id=group_id)
    await state.update_data(
        {'message': message, 'tg_id': tg_id, 'table': table, 'action': command}
    )
    await state.set_state(TasksState.Week)
    weeks = table.list_weeks()
    await message.reply('Select a week', reply_markup=week_selector(weeks))


@tasks_router.entry_point(command=CommandName.DECLARE.value)
async def declare_command_handler(message: Message, state: FSMContext):
    await process_entry_point(message, state, CommandName.DECLARE)


@tasks_router.entry_point(command=CommandName.RECALL.value)
async def recall_command_handler(message: Message, state: FSMContext):
    await process_entry_point(message, state, CommandName.RECALL)


@tasks_router.callback_query(TasksState.Week, WeekCallback.filter())
@tasks_router.callback_query(TasksState.Task, WeekCallback.filter())
async def select_week_handler(query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    group_id, student_name = data['group_id'], data['student_name']
    original_message: Message = data['message']
    table: Table = data['table']
    action: CommandName = data['action']
    week_name = WeekCallback.unpack(query.data).week_name

    tasks = (
        table.list_available_week_tasks(group_id, student_name, week_name)
        if action is CommandName.DECLARE
        else table.list_recallable_week_tasks(group_id, student_name, week_name)
    )
    if len(tasks) == 0:
        await query.answer('Selected week has no tasks to offer :(')
        return
    await query.answer(f'Selected week {week_name}')
    await state.set_state(TasksState.Task)

    await state.update_data(
        {'week_name': week_name, 'tasks': tasks, 'selection': set()}
    )
    if 'task_selector_message' in data:
        await data['task_selector_message'].delete()
    task_selector_message = await original_message.reply(
        'Pick tasks to mark as solved and press \'Commit\'',
        reply_markup=task_selector(week_name, tasks, set()),
    )
    await state.update_data({'task_selector_message': task_selector_message})


@tasks_router.callback_query(TasksState.Task, TaskCallback.filter())
async def check_task_handler(query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    task_name = TaskCallback.unpack(query.data).task_name
    week_name = data['week_name']
    tasks: list[str] = data['tasks']
    selection: set[str] = data['selection']

    if task_name not in selection:
        selection.add(task_name)
    else:
        selection.remove(task_name)

    task_selector_message: Message = data['task_selector_message']
    await state.update_data({'selection': selection})
    await task_selector_message.edit_reply_markup(
        reply_markup=task_selector(week_name, tasks, selection)
    )


@tasks_router.callback_query(TasksState.Task, CommitCallback.filter())
async def commit_handler(query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    group_id, student_name, week_name = (
        data['group_id'],
        data['student_name'],
        data['week_name'],
    )
    table: Table = data['table']
    selection: set[str] = data['selection']
    action: CommandName = data['action']

    task_list = [(week_name, task) for task in selection]
    if action is CommandName.DECLARE:
        result = table.mark_tasks(group_id, student_name, task_list)
    else:
        result = table.unmark_tasks(group_id, student_name, task_list)

    original_message: Message = data['message']
    if len(result[MarkingResult.NO_CHANGES]) > 0:
        tasks_string = ', '.join(
            sorted([task[1] for task in result[MarkingResult.NO_CHANGES]])
        )
        await original_message.reply(f'Tasks {tasks_string} were skipped')
    if len(result[MarkingResult.UNAVAILABLE]) > 0:
        tasks_string = ', '.join(
            sorted([task[1] for task in result[MarkingResult.UNAVAILABLE]])
        )
        await original_message.reply(f'You can not {action.value} tasks {tasks_string}')

    task_selector_message: Message = data['task_selector_message']
    await task_selector_message.delete()
    await query.answer('Done!')
    await state.clear()

from dataclasses import dataclass, field

import emoji
from aiogram import Bot
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from algobot.data.connectors.tables import ChangeMarkingVerdict, Table, MarkStatus
from algobot.data.connectors.users import Users
from algobot.data.helpers.defaults import get_default_course
from tgutils.consts.aliases import KeyboardBuilder, Button
from tgutils.consts.buttons import FAIL_MINI, OK_MINI, RECORD
from tgutils.context import Context
from tgutils.context.internal import ContextTransition
from tgutils.context.types import Response
from tgutils.pages.paginator import VerticalPaginator, DEFAULT_MAX_ROWS
from .feature import EnablerRouter
from .register import CommandName as RegisterCommandNames

tasks_router = EnablerRouter('tasks', enabled_by_default=True)


class WeekPaginator(VerticalPaginator[str]):
    def __init__(self):
        VerticalPaginator.__init__(self, DEFAULT_MAX_ROWS - 1, 2)

    class WeekCallback(CallbackData, prefix='tasks-week'):
        week: str

    def make_button(self, item: str) -> Button:
        return Button(text=item, callback_data=self.WeekCallback(week=item).pack())


class TaskPaginator(VerticalPaginator[str]):
    def __init__(self):
        self.marked: set[str] = set()
        VerticalPaginator.__init__(self, DEFAULT_MAX_ROWS - 1, 3)

    class TaskCallback(CallbackData, prefix='tasks-tasks'):
        task: str
        mark: bool

    def make_button(self, item: str) -> Button:
        marked = item in self.marked
        text = (OK_MINI if marked else FAIL_MINI) + item
        return Button(text=text, callback_data=TaskPaginator.TaskCallback(task=item, mark=not marked).pack())


@dataclass
class TasksContext(Context):
    weeks: WeekPaginator = field(default_factory=WeekPaginator)
    tasks: TaskPaginator = field(default_factory=TaskPaginator)

    group_id: str = None
    student_name: str = None
    table: Table = None
    selected_week: str = None


TasksContext.prepare(tasks_router)


class TasksState(StatesGroup):
    WEEK = State()
    TASKS = State()


@tasks_router.callback_query(WeekPaginator.callback().filter(), TasksState.WEEK)
@TasksContext.inject
async def handle_week_pagination(context: TasksContext, query: CallbackQuery):
    context.weeks.advance(query)
    await context.advance(TasksState.WEEK)


@tasks_router.callback_query(TaskPaginator.callback().filter(), TasksState.TASKS)
@TasksContext.inject
async def handle_task_pagination(context: TasksContext, query: CallbackQuery):
    context.tasks.advance(query)
    await context.advance(TasksState.TASKS)


@tasks_router.entry_point(command='tasks')
@TasksContext.entry_point
async def handle_command(context: TasksContext, message: Message):
    tg_id = message.from_user.id
    if user := Users.get_user(tg_id):
        context.group_id, context.student_name = user['group_id'], user['student_name']
        context.table = Table.get_table(get_default_course(context.group_id), group_id=context.group_id)
        await context.advance(TasksState.WEEK, sender=message.reply, cause=message)
        return

    await message.reply(f'Please, first use /{RegisterCommandNames.REGISTER} to introduce yourself')
    await context.finish()


@TasksContext.register(TasksState.WEEK)
def week_menu(context: TasksContext) -> Response:
    if context.last_transition != ContextTransition.HOLD:
        context.weeks.items = context.table.list_weeks()

    keyboard = KeyboardBuilder()
    context.weeks.to_builder(keyboard)
    keyboard.row(context.menu_button(context.Action.FINISH))
    return Response(
        text='Choose a week',
        markup=keyboard.as_markup()
    )


@tasks_router.callback_query(TasksState.WEEK, WeekPaginator.WeekCallback.filter())
@TasksContext.inject
async def handle_week_select(context: TasksContext, query: CallbackQuery):
    context.selected_week = WeekPaginator.WeekCallback.unpack(query.data).week
    await context.advance(TasksState.TASKS)


class CommitCallback(CallbackData, prefix='tasks-commit'):
    pass


@TasksContext.register(TasksState.TASKS)
def task_menu(context: TasksContext) -> Response:
    if context.last_transition != ContextTransition.HOLD:
        tasks = context.table.list_week_tasks(
            context.group_id,
            context.student_name,
            context.selected_week
        )
        context.tasks.items = []
        context.tasks.marked = set()
        for task, status in tasks:
            context.tasks.items.append(task)
            if status in (MarkStatus.MARKED, MarkStatus.MARKED_LOCKED):
                context.tasks.marked.add(task)

    keyboard = KeyboardBuilder()
    context.tasks.to_builder(keyboard)
    keyboard.row(
        context.menu_button(context.Action.BACK),
        Button(
            text=f'{RECORD} Commit',
            callback_data=CommitCallback().pack()
        ),
    )
    return Response(
        text='Change marking of tasks and press Commit',
        markup=keyboard.as_markup()
    )


@tasks_router.callback_query(TasksState.TASKS, TaskPaginator.TaskCallback.filter())
@TasksContext.inject
async def handle_task_trigger(context: TasksContext, query: CallbackQuery):
    data = TaskPaginator.TaskCallback.unpack(query.data)
    task, mark = data.task, data.mark
    if mark:
        context.tasks.marked.add(task)
    else:
        context.tasks.marked.remove(task)
    await context.advance(TasksState.TASKS)


@tasks_router.callback_query(TasksState.TASKS, CommitCallback.filter())
@TasksContext.inject
async def handle_commit(context: TasksContext, query: CallbackQuery, bot: Bot):
    task_list = [
        (context.selected_week, task, task in context.tasks.marked)
        for task in context.tasks.items
    ]
    result = context.table.update_tasks(context.group_id, context.student_name, task_list)

    await query.answer('Done!')
    if len(result[ChangeMarkingVerdict.UNAVAILABLE]) > 0:
        skipped = [
            f'+{task}' if task in context.tasks.marked else f'-{task}'
            for _, task, _ in result[ChangeMarkingVerdict.UNAVAILABLE]
        ]
        tasks_string = ', '.join(sorted(skipped))
        await bot.send_message(
            context.chat_id,
            f'Tasks {tasks_string} are locked, send this message to your teacher to update manually'
        )

    await context.finish()

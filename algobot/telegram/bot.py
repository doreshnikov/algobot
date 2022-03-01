from __future__ import annotations

from typing import Callable

import yaml
import logging

from telebot import TeleBot
from telebot.types import Message

from algobot.common.config import Config
from algobot.telegram.filters.admin import AdminFilter
from algobot.telegram.validation.validation import Validator, ValidationError

from algobot.db.registry import Registry, DummyRegistry, TaskStatus
from algobot.db.mapping import Mapping, RequestFail

logger = logging.getLogger(__name__)


def report_validation(f):
    def wrapper(self: AlgoBot, message: Message, *args):
        try:
            result = f(self, message, *args)
            return result
        except ValidationError as e:
            self.bot.send_message(message.chat.id, e.message)
            return e

    return wrapper


def ensure_registration(f):
    def wrapper(self: AlgoBot, message: Message):
        user = self.mapping.query_by_id(message.from_user.id)
        self.validator.true(user is not None, 'Please use /register to introduce yourself')
        return f(self, message, user)

    return wrapper


class AlgoBot:
    help_message = [
        'Use /register to introduce yourself and /add to add tasks.',
        'All commands are available in the menu.',
        '',
        'Link to the spreadsheet is <b><a href="https://docs.google.com/spreadsheets/'
        'd/1oLVLn7yeqslMXiXhsPQ66XrfVtgAM_-HX18QiZG98nQ/edit">here</a></b>.'
    ]

    def __init__(self, registry: Registry, mapping: Mapping):
        self.registry = registry
        self.validator = Validator(registry)
        self.mapping = mapping

        logger.info('All connected')
        self.bot = TeleBot(Config().telegram['token'])
        self.bot.add_custom_filter(AdminFilter())
        for key, handler in self._active_methods.items():
            self.bot.register_message_handler(handler, commands=[key])
        self.bot.register_message_handler(self._help, commands=['start', 'help'])
        logger.info('All handlers installed')

    @property
    def _active_methods(self) -> dict[str, Callable]:
        return {
            'register': self._register,
            'unregister': self._unregister,
            'add': self._add_tasks,
            'delete': self._delete_tasks,
            'show': self._show_tasks
        }

    def _help(self, message: Message):
        self.bot.send_message(
            message.chat.id, '\n'.join(AlgoBot.help_message),
            parse_mode='HTML', disable_web_page_preview=True
        )

    @report_validation
    def _register(self, message: Message):
        logger.info('Register called')
        items = message.text.split()[1:]
        self.validator.true(len(items) >= 2, 'Please use format \'/register <group> <name>\'')
        group_id = self.validator.group_id(items[0])
        student_name = self.validator.student_name(group_id, ' '.join(items[1:]))

        tg_ref = message.from_user.username
        if tg_ref is None:
            tg_ref = message.from_user.full_name
        self.validator.request_result(self.mapping.register(
            tg_id=message.from_user.id, tg_ref=tg_ref,
            group_id=group_id, student_name=student_name
        ))
        self.bot.send_message(message.chat.id, f'Registered as \'{student_name}\'')

    @report_validation
    def _unregister(self, message: Message):
        logger.info('Unregister called')
        items = message.text.split()[1:]
        self.validator.true(len(items) == 0, 'No parameters for \'/unregister\' expected')
        self.validator.request_result(self.mapping.unregister(tg_id=message.from_user.id))
        self.bot.send_message(message.chat.id, 'Successfully unregistered')

    def _filter_tasks(
            self, group_id: str, student_name: str,
            task_ids: list[str], extra_ignore: list[TaskStatus] | None = None
    ) -> tuple[list[str], list[str]]:
        if extra_ignore is None:
            extra_ignore = []
        ok_ids, ignored_ids = [], []
        for task_id in task_ids:
            gs = self.registry.task_status(group_id, task_id)
            os = self.registry.students_task_status(group_id, student_name, task_id)
            if TaskStatus.frozen(gs, os):
                ignored_ids.append(task_id)
            elif os not in extra_ignore:
                ok_ids.append(task_id)
        return ok_ids, ignored_ids

    @staticmethod
    def _describe(task_ids: list[str]):
        if not task_ids:
            return 'no tasks'
        return ('task ' if len(task_ids) < 2 else 'tasks ') + ' '.join(task_ids)

    @report_validation
    @ensure_registration
    def _add_tasks(self, message: Message, user):
        logger.info('Add called')
        items = message.text.split()[1:]
        self.validator.true(len(items) > 0, 'No tasks specified')

        group_id, student_name = user.group_id, user.student_name
        task_ids = self.validator.task_ids(group_id, items)
        ok_ids, ignored_ids = self._filter_tasks(group_id, student_name, task_ids, extra_ignore=[TaskStatus.MARKED])
        self.validator.request_result(self.registry.add_tasks(
            group_id=group_id, student_name=student_name,
            task_ids=ok_ids
        ))
        reply = f'Added {AlgoBot._describe(ok_ids)}'
        if ignored_ids:
            reply += f', ignored frozen/already added {AlgoBot._describe(ignored_ids)}'
        self.bot.send_message(message.from_user.id, reply)

    @report_validation
    @ensure_registration
    def _delete_tasks(self, message: Message, user):
        logger.info('Delete called')
        items = message.text.split()[1:]
        self.validator.true(len(items) > 0, 'No tasks specified')

        group_id, student_name = user.group_id, user.student_name
        task_ids = self.validator.task_ids(group_id, items)
        ok_ids, ignored_ids = self._filter_tasks(group_id, student_name, task_ids, extra_ignore=[TaskStatus.EMPTY])
        self.validator.request_result(self.registry.delete_tasks(
            group_id=group_id, student_name=student_name,
            task_ids=ok_ids
        ))
        reply = f'Deleted {AlgoBot._describe(ok_ids)}'
        if ignored_ids:
            reply += f', ignored frozen {AlgoBot._describe(ignored_ids)}'
        self.bot.send_message(message.from_user.id, reply)

    @report_validation
    @ensure_registration
    def _show_tasks(self, message: Message, user):
        logger.info('Show called')
        items = message.text.split()[1:]
        self.validator.true(len(items) <= 1, 'Not more than one parameter (<week>) expected')
        week_id = items[0] if items else None

        task_ids = self.validator.request_result(self.registry.list_students_tasks(
            week_id=week_id,
            group_id=user.group_id, student_name=user.student_name
        ))
        reply = f'You have added {AlgoBot._describe(task_ids)}'
        if week_id:
            reply += f' during week {week_id}'
        self.bot.send_message(message.from_user.id, reply)

    def run(self):
        self.bot.infinity_polling()

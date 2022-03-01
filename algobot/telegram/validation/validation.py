from __future__ import annotations

from typing import Any

import re
import logging

from telebot import TeleBot
from telebot.types import Message

from algobot.db.registry import Registry
from algobot.db.mapping import RequestResult, RequestFail

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    def __init__(self, message):
        self.message = message
        logger.info(f'Validation error: {message}')
        super().__init__(message)


class Validator:
    def __init__(self, registry: Registry):
        self.registry = registry

    @staticmethod
    def true(condition: bool, message: str):
        if not condition:
            raise ValidationError(message)

    def group_id(self, group_id: str) -> str:
        if not re.fullmatch(r'M3\d3\d\d?', group_id):
            raise ValidationError(f'Token \'{group_id}\' is not a valid group id')
        if group_id not in self.registry.list_groups():
            raise ValidationError(f'Group \'{group_id}\' not found')
        return group_id

    def student_name(self, group_id: str, student_name: str) -> str:
        """Assuming :param group_id is already validated"""
        if not re.fullmatch(r'[а-яА-Я]+( [а-яА-Я]+)*', student_name):
            raise ValidationError(f'Token \'{student_name}\' is not a valid name')
        student_list = self.registry.list_group(group_id)
        candidates = [name for name in student_list if student_name in name]
        if not candidates:
            raise ValidationError(f'No students in group \'{group_id}\' with such name found')
        if len(candidates) > 1:
            raise ValidationError(f'More than one student in group \'{group_id}\' fits such name')
        return candidates[0]

    def task_ids(self, group_id: str, tasks: list[str]) -> list[str]:
        pattern = r'[1-9]\d*\.[1-9]\d*[a-z]?'
        pattern = f'{pattern}(-{pattern})?'
        all_tasks = self.request_result(self.registry.list_tasks(group_id, week_id=None))

        def check_one(task):
            if task not in all_tasks:
                raise ValidationError(f'Task \'{task}\' not found')
            return all_tasks.index(task)

        task_ids = []
        for task in tasks:
            if not re.fullmatch(pattern, task):
                raise ValidationError(f'Token \'{task}\' is not a valid task or task range')
            if '-' in task:
                f_idx, t_idx = map(check_one, task.split('-'))
                task_ids += all_tasks[f_idx:t_idx + 1]
            else:
                check_one(task)
                task_ids.append(task)

        task_ids = list(set(task_ids))

        def key(tid: str):
            week, no = tid.split('.')
            logger.warning(f'Sorting {tid}, {week}/{no}')
            flag, week = (0, int(week)) if week.isnumeric() else (1, week)
            no, sub = (int(no), '') if no.isnumeric() else (int(no[:-1]), no[-1])
            return flag, week, no, sub

        task_ids.sort(key=key)
        return task_ids

    @staticmethod
    def request_result(result: Any | RequestResult):
        if isinstance(result, RequestFail):
            raise ValidationError(result.message)
        return result

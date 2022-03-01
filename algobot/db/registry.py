from __future__ import annotations

import re
import json
from gspread import service_account, Spreadsheet, Cell
from gspread.exceptions import APIError, GSpreadException

import logging
from threading import Thread, Lock
from time import sleep

from typing import Callable
from abc import ABC, abstractmethod
from enum import Enum
from inspect import getmembers, isfunction

from algobot.common.config import Config
from algobot.common.feedback import RequestResult, RequestSuccess, RequestFail

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    EMPTY = ''
    MARKED = '+'
    SELECTED = '!'
    ON_HOLD = '~'
    FAILED = '-'
    FULL = 'x'
    HALF = 'y'

    @staticmethod
    def of(value: str | None) -> TaskStatus:
        if value is None:
            return TaskStatus.EMPTY
        return TaskStatus(value)

    @staticmethod
    def frozen(global_status: TaskStatus, own_status: TaskStatus):
        return global_status == TaskStatus.FULL or \
               own_status in [TaskStatus.SELECTED, TaskStatus.FAILED, TaskStatus.HALF]


class Registry(ABC):
    @abstractmethod
    def list_groups(self) -> list[str] | RequestResult:
        pass

    @abstractmethod
    def list_group(self, group_id: str) -> list[str] | RequestResult:
        pass

    @abstractmethod
    def list_tasks(self, group_id: str, week_id: str | None) -> list[str] | RequestResult:
        pass

    @abstractmethod
    def task_status(self, group_id: str, task_id: str) -> \
            TaskStatus.EMPTY | TaskStatus.FULL | TaskStatus.HALF | TaskStatus.SELECTED | RequestResult:
        pass

    @abstractmethod
    def list_students_tasks(self, week_id: str | None, group_id: str, student_name: str) -> list[str] | RequestResult:
        pass

    @abstractmethod
    def students_task_status(self, group_id: str, student_name: str, task_id: str) -> TaskStatus | RequestResult:
        pass

    @abstractmethod
    def add_tasks(self, group_id: str, student_name: str, task_ids: list[str]) -> RequestResult:
        pass

    @abstractmethod
    def delete_tasks(self, group_id: str, student_name: str, task_ids: list[str]) -> RequestResult:
        pass


class DummyRegistry(Registry):
    def __init__(self):
        with open('resources/groups.json', encoding='utf-8') as groups:
            self.groups: dict[str, list[str]] = json.load(groups)
        with open('resources/tasks.json') as tasks:
            self.tasks: list[list[str]] = json.load(tasks)
        self.students_tasks: dict[tuple[str, str], list[str]] = dict()

    def list_groups(self) -> list[str]:
        groups = list(self.groups.keys())
        groups.sort()
        return groups

    def list_group(self, group_id: str) -> list[str]:
        return self.groups[group_id]

    def list_tasks(self, group_id: str, week_id: str | None) -> list[str]:
        if not week_id:
            return sum(self.tasks, start=[])
        return self.tasks[int(week_id)]

    def task_status(self, group_id: str, task_id: str) -> TaskStatus.EMPTY:
        return TaskStatus.EMPTY

    def list_students_tasks(self, week_id: str | None, group_id: str, student_name: str) -> list[str]:
        task_ids = self.students_tasks.get((group_id, student_name), [])
        if not week_id:
            return task_ids
        return [task_id for task_id in task_ids if task_id.startswith(week_id + '.')]

    def students_task_status(self, group_id: str, student_name: str, task_id: str) -> TaskStatus:
        # noinspection PyTypeChecker
        return TaskStatus.MARKED if task_id in self.list_students_tasks(None, group_id, student_name) \
            else TaskStatus.EMPTY

    def add_tasks(self, group_id: str, student_name: str, task_ids: list[str]) -> RequestResult:
        key = (group_id, student_name)
        if key not in self.students_tasks:
            self.students_tasks[key] = []
        for task_id in task_ids:
            if task_id not in self.students_tasks[key]:
                self.students_tasks[key].append(task_id)
        self.students_tasks[key].sort()
        return RequestSuccess()

    def delete_tasks(self, group_id: str, student_name: str, task_ids: list[str]) -> RequestResult:
        key = (group_id, student_name)
        if key not in self.students_tasks:
            return RequestFail('You haven\'t added any tasks yet')
        for task_id in task_ids:
            if task_id in self.students_tasks[key]:
                self.students_tasks[key].remove(task_id)
        self.students_tasks[key].sort()
        return RequestSuccess()


def forward_gspread_errors(cls: type) -> type:
    def decorator(f: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            try:
                result = f(*args, **kwargs)
                return result
            except APIError as _:
                return RequestFail('API requests limit reached, try one minute later')
            except GSpreadException as e:
                return RequestFail(str(e))

        return wrapper

    for name, method in getmembers(cls, isfunction):
        if not name.startswith('_'):
            setattr(cls, name, decorator(method))
    return cls


@forward_gspread_errors
class SheetsRegistry(Registry):
    def __init__(self):
        config = Config()
        cred_file = config.sheets['credentials_file']
        self.service = service_account(filename=cred_file)
        self.table: Spreadsheet = self.service.open_by_key(config.sheets['sheet_id'])
        logger.info('Sheets connected')

        self.lock = Lock()
        self.groups_cache: dict[str, list[str]] = dict()
        self.tasks_cache: dict[str, list[str]] = dict()
        self.tables_cache: dict[str, list[list[str]]] = dict()

        self.scheduled_updates: dict[str, list[dict]] = dict()
        self.scheduled_deletes: dict[str, list[str]] = dict()
        self.raw_updates: dict[str, list[Cell]] = dict()

        worker = self.very_ineffective_worker(timeout=5)

    def very_ineffective_worker(self, timeout: int, steps: int = 4):
        def worker():
            it = 0
            while True:
                if it == 0:
                    self._reload_cache()
                sleep(timeout)
                self._dump_updates()
                it = (it + 1) if it + 1 < steps else 0

        thread = Thread(target=worker)
        thread.start()
        return thread

    # @repeating_thread(timeout=10)
    def _reload_cache(self):
        logger.info('Cache reloading...')
        self.lock.acquire()
        logger.info('Lock acquired for cache reload')
        self.groups_cache = dict()
        groups = self.list_groups()
        self.tables_cache = {group_id: self.table.worksheet(group_id).get_all_values() for group_id in groups}
        self.groups_cache = {group_id: self._get_column_values(group_id, 1)[2:-2] for group_id in groups}
        self.tasks_cache = {group_id: [task_id for task_id in self._get_row_values(group_id, 2)[5:]
                                       if not task_id.endswith('Σ')]
                            for group_id in groups}
        self.lock.release()
        logger.info('Cache reloaded, lock released')

    def _plan_updates(self, group_id: str, cells: list[Cell]):
        logger.info('Planning updates...')
        self.lock.acquire()
        logger.info('Lock acquired for updates planning')
        if group_id not in self.scheduled_updates:
            self.scheduled_updates[group_id] = []
            self.scheduled_deletes[group_id] = []
            self.raw_updates[group_id] = []
        for cell in cells:
            if cell.value:
                self.scheduled_updates[group_id].append({
                    'range': cell.address,
                    'values': [[cell.value]]
                })
            else:
                self.scheduled_deletes[group_id].append(cell.address)
        self.raw_updates[group_id] += cells
        self.lock.release()
        logger.info('Updates planned, lock released')

    def _dump_updates(self):
        logger.info('Dumping updates...')
        self.lock.acquire()
        logger.info('Lock acquired for updates dumping')
        for group_id in self.list_groups():
            if group_id not in self.raw_updates:
                continue
            sheet = self.table.worksheet(group_id)
            sheet.batch_update(self.scheduled_updates[group_id])
            sheet.batch_clear(self.scheduled_deletes[group_id])

            table = self.tables_cache.get(group_id)
            if table:
                for cell in self.raw_updates[group_id]:
                    table[cell.row - 1][cell.col - 1] = cell.value

            self.scheduled_updates.pop(group_id)
            self.scheduled_deletes.pop(group_id)
            self.raw_updates.pop(group_id)
        self.lock.release()
        logger.info('Updates dumped, lock released')

    def list_groups(self) -> list[str] | RequestResult:
        group_ids = list(self.groups_cache.keys())
        if not group_ids:
            group_ids = [sheet.title for sheet in self.table.worksheets()
                         if re.fullmatch(r'M3\d3\d\d?', sheet.title)]
        group_ids.sort()
        return group_ids

    def list_group(self, group_id: str) -> list[str] | RequestResult:
        group_names = self.groups_cache.get(group_id)
        if not group_names:
            sheet = self.table.worksheet(group_id)
            group_names = sheet.col_values(1)[2:-2]
        return group_names

    def list_tasks(self, group_id: str, week_id: str | None) -> list[str] | RequestResult:
        tasks = self.tasks_cache.get(group_id)
        if not tasks:
            sheet = self.table.worksheet(group_id)
            tasks = [task_id for task_id in sheet.row_values(2)[5:] if not task_id.endswith('Σ')]
        if not week_id:
            return tasks
        return [task_id for task_id in tasks if task_id.startswith(week_id + '.')]

    def _get_student_row(self, group_id: str, student_name: str) -> int:
        students = self.list_group(group_id)
        return 3 + students.index(student_name)

    def _get_task_column(self, group_id: str, task_id: str) -> int:
        tasks = self.list_tasks(group_id, None)
        return 6 + tasks.index(task_id) + int(task_id.split('.')[0]) - 1  # TODO fix this shit

    def _get_row_values(self, group_id: str, row: int) -> list[str]:
        all_table = self.tables_cache.get(group_id)
        if not all_table:
            return self.table.worksheet(group_id).row_values(row)
        return all_table[row - 1]

    def _get_column_values(self, group_id: str, column: int) -> list[str]:
        all_table = self.tables_cache.get(group_id)
        if not all_table:
            return self.table.worksheet(group_id).col_values(column)
        return [all_table[i][column - 1] for i in range(len(all_table))]

    def _get_cell_value(self, group_id: str, row: int, column: int) -> str:
        all_table = self.tables_cache.get(group_id)
        if not all_table:
            return self.table.worksheet(group_id).cell(row, column).value
        return all_table[row - 1][column - 1]

    def task_status(self, group_id: str, task_id: str) \
            -> TaskStatus.EMPTY | TaskStatus.FULL | TaskStatus.HALF | TaskStatus.SELECTED | RequestResult:
        column = self._get_task_column(group_id, task_id)
        statuses = self._get_column_values(group_id, column)[2:-2]
        result = TaskStatus.EMPTY
        for status in statuses:
            if status == TaskStatus.FULL.value:
                return TaskStatus.FULL
            if status == TaskStatus.HALF.value and result != TaskStatus.SELECTED.value:
                result = TaskStatus.HALF
            elif status == TaskStatus.SELECTED.value:
                result = TaskStatus.SELECTED
        return result

    def list_students_tasks(self, week_id: str | None, group_id: str, student_name: str) -> list[str] | RequestResult:
        row = self._get_student_row(group_id, student_name)
        tasks = self._get_row_values(group_id, 2)[5:]
        statuses = self._get_row_values(group_id, row)[5:]
        result = []
        ok_statuses = list(map(lambda it: it.value,
                               (TaskStatus.MARKED, TaskStatus.HALF, TaskStatus.FULL, TaskStatus.SELECTED)))
        for task, status in zip(tasks, statuses):
            if status in ok_statuses and (not week_id or task.startswith(week_id + '.')):
                result.append(task)
        return result

    def students_task_status(self, group_id: str, student_name: str, task_id: str) -> TaskStatus | RequestResult:
        row = self._get_student_row(group_id, student_name)
        column = self._get_task_column(group_id, task_id)
        return TaskStatus.of(self._get_cell_value(group_id, row, column))

    def add_tasks(self, group_id: str, student_name: str, task_ids: list[str]) -> RequestResult:
        row = self._get_student_row(group_id, student_name)
        tasks = self.list_tasks(group_id, None)
        indices = [self._get_task_column(group_id, task_id) for task_id in task_ids]
        self._plan_updates(group_id, [Cell(row, column, TaskStatus.MARKED.value) for column in indices])
        return RequestSuccess()

    def delete_tasks(self, group_id: str, student_name: str, task_ids: list[str]) -> RequestResult:
        row = self._get_student_row(group_id, student_name)
        indices = [self._get_task_column(group_id, task_id) for task_id in task_ids]
        self._plan_updates(group_id, [Cell(row, column, TaskStatus.EMPTY.value) for column in indices])
        return RequestSuccess()

import json5

from enum import Enum, EnumType
from dataclasses import dataclass, field
from pathlib import Path
from cachetools.func import ttl_cache
from gspread.utils import Dimension
from gspread.cell import Cell

from algobot.config import sheets_config
from algobot.drivers.google import sheets_driver
from .students import Students


class UnknownCourseError(Exception):
    def __init__(self, course: str, group_ids: list[str]):
        self.course = course
        self.group_ids = group_ids
        super().__init__(f'Course \'{course}\' for groups {group_ids} not found')


class MultipleCoursesError(Exception):
    def __init__(self, course: str, group_ids: list[str]):
        self.course = course
        self.group_id = group_ids
        super().__init__(
            f'Course \'{course}\' and group {group_ids} appear in config multiple times'
        )


class UnknownTemplateError(Exception):
    def __init__(self, template_name: str):
        self.template_name = template_name
        super().__init__(f'Unknown template name \'{template_name}\'')


class InconsistentMappingError(Exception):
    def __init__(self, group_ids: list[str], mapped_names: set[str]):
        self.group_ids = group_ids
        self.mapped_names = mapped_names
        super().__init__(
            f'Groups {group_ids} have inconsistent sheet name mapping: {mapped_names}'
        )


class DefaultCellStatus(Enum):
    NONE = ''
    SOLVED = '+'
    CHOSEN = '!'
    FULL = 'x'
    HALF = 'y'
    THINK = '~'
    FAIL = '-'


class MarkingResponse(Enum):
    OK = 'OK'
    ALREADY_MARKED = 'already marked'
    UNAVAILABLE = 'unavailable'


class UnmarkingResponse(Enum):
    OK = 'OK'
    UNAVAILABLE = 'unavailable'


@dataclass
class Mapping:
    students: list[tuple[str, str]] = field(default_factory=list)
    weeks: list[str] = field(default_factory=list)
    weeks_tasks: dict[str, list[str]] = field(default_factory=dict)

    def student_row(self, group: str, student_name: str) -> int:
        return self.students.index((group, student_name))

    def week_number(self, week: str) -> int:
        return self.weeks.index(week)

    def task_number(self, week: str, task: str) -> int:
        return self.weeks_tasks[week].index(task)

    def task_column(self, week: str, task: str) -> int:
        task_column = 0
        for other_week in self.weeks:
            if other_week != week:
                task_column += len(self.weeks_tasks[other_week]) + 1
            else:
                task_column += self.task_number(week, task)
                break
        return task_column


# noinspection PyUnresolvedReferences
class Table:
    def __init__(self, course: str, **kwargs):
        if len(kwargs) != 1 or ('group_id' not in kwargs and 'group_ids' not in kwargs):
            raise ValueError(
                'Expected either `group_id: str` or `group_ids: list[str]`'
            )
        self.group_ids = kwargs.get('group_ids', [kwargs['group_id']])
        if len(self.group_ids) == 0:
            raise ValueError('Expected at least one group per table')

        self.course = course
        self.config = None
        for course_config in sheets_config['courses']:
            if course_config['course'] == course and all(
                [group_id in course_config['groups'] for group_id in self.group_ids]
            ):
                if self.config:
                    raise MultipleCoursesError(course, self.group_ids)
                self.config = course_config
        if not self.config:
            raise UnknownCourseError(course, self.group_ids)

        self.sheet_id = self.config['sheet_id']
        self.spreadsheet = sheets_driver.open_by_key(self.sheet_id)

        templates_dir = Path() / 'resources' / 'sheets' / 'templates'
        template_name = self.config['template']
        template_path = templates_dir / f'{template_name}.json5'
        if not template_path.is_file():
            raise UnknownTemplateError(template_name)
        with open(template_path) as template_file:
            self.template = json5.load(template_file)

        self.group_name = self.group_ids[0]
        group_mapping = self.template.get('group_sheet_mapping')
        if group_mapping:
            if 'group_column' not in self.template:
                raise ValueError(
                    'Property group_column should be provided in template when groups are merged'
                )
            group_names = {group_mapping.get(group_id) for group_id in self.group_ids}
            if len(group_names) > 1:
                raise InconsistentMappingError(self.group_ids, group_names)
            self.group_name = group_names.pop()
        self.table = self.spreadsheet.worksheet(self.group_name)
        self.markers = self._create_markers()
        self.mapping = None
        self.reload(update_db=False)

    def _create_markers(self) -> EnumType:
        markers = {item.name: item.value for item in DefaultCellStatus}
        if 'markers' in self.template:
            for name, value in self.template['markers'].items():
                markers[name.upper()] = value
        return Enum('CellStatus', markers)

    @staticmethod
    def a1r1_notation(row: int, column: int):
        alpha = ord('Z') - ord('A') + 1
        column -= 1
        column_name = ''
        while column > 0:
            column_name += chr(ord('A') + column % alpha)
            column //= alpha
        if column_name == '':
            column_name = 'A'
        return f'${column_name[::-1]}${row}'

    @property
    def index_columns(self) -> int:
        return self.template['index_columns']

    @property
    def name_column(self) -> int:
        return self.template['name_column'] - 1

    @property
    def header_rows(self) -> int:
        return self.template['header_rows']

    @property
    def week_row(self) -> int:
        return self.template['week_row'] - 1

    @property
    def tasks_row(self) -> int:
        return self.template['tasks_row'] - 1

    @property
    def week_delta(self) -> int:
        return self.template['week_delta']

    @ttl_cache(maxsize=10, ttl=5)
    def get_table_values(self, *args, **kwargs):
        return self.table.get_values(*args, **kwargs)

    def _reload_header(self):
        header: list[list] = self.get_table_values(
            f'{Table.a1r1_notation(1, 1)}:'
            f'{Table.a1r1_notation(self.header_rows, self.table.col_count)}'
        )
        week_name, tasks = '', []
        for column in range(self.index_columns, len(header[0])):
            if header[self.week_row][column] != '':
                if len(tasks) > 0:
                    self.mapping.weeks.append(week_name)
                    self.mapping.weeks_tasks[week_name] = tasks[: -self.week_delta]
                week_name = header[self.week_row][column]
                tasks = [header[self.tasks_row][column]]
            else:
                tasks.append(header[self.tasks_row][column])
        self.mapping.weeks.append(week_name)
        self.mapping.weeks_tasks[week_name] = tasks[: -self.week_delta]

    def _reload_index(self):
        index = self.get_table_values(
            f'{Table.a1r1_notation(1, 1)}:'
            f'{Table.a1r1_notation(self.table.row_count, self.index_columns)}'
        )
        group_column = (
            None
            if 'group_column' not in self.template
            else index[0].index(self.template['group_column'])
        )
        footer_rows = self.template['footer_rows']

        def footer_condition(row):
            if isinstance(footer_rows, int):
                return row >= len(index) - footer_rows
            return eval(footer_rows['condition'].replace('$', repr(index[row][0])))

        for row in range(self.header_rows, len(index)):
            if footer_condition(row):
                break
            student_name = index[row][self.name_column]
            group = index[row][group_column] if group_column else self.group_ids[0]
            self.mapping.students.append((group, student_name))

    def reload(self, update_db: bool = True):
        self.mapping = Mapping()
        self._reload_header()
        self._reload_index()
        if update_db:
            for group_id in self.group_ids:
                Students.delete_group_students(group_id)
            for group, student_name in self.mapping.students:
                Students.register_student(group, student_name)

    def _check_marking(self, column_data: list, row: int) -> MarkingResponse:
        if column_data[row] != self.markers.NONE.value:
            return MarkingResponse.ALREADY_MARKED
        ok_markers = [self.markers.CHOSEN, self.markers.FULL, self.markers.HALF]
        if any([value in ok_markers for value in column_data]):
            return MarkingResponse.FROZEN
        return MarkingResponse.OK

    def mark_tasks(self, group: str, student_name: str, tasks: list[tuple[str, str]]):
        table_data = self.get_table_values(
            f'{Table.a1r1_notation(self.header_rows + 1, self.index_columns + 1)}:'
            f'{Table.a1r1_notation(self.header_rows + len(self.mapping.students), self.table.col_count)}',
            major_dimension=Dimension.cols,
        )
        student_row = self.mapping.student_row(group, student_name)
        statuses = {status: [] for status in MarkingResponse}
        for week, task in tasks:
            task_column = self.mapping.task_column(week, task)
            statuses[self._check_marking(table_data[task_column], student_row)].append(
                (week, task, task_column)
            )

        self.table.update_cells(
            [
                Cell(
                    self.header_rows + student_row + 1,
                    self.index_columns + task[2] + 1,
                    self.markers.SOLVED.value,
                )
                for task in statuses[MarkingResponse.OK]
            ]
        )
        return statuses


if __name__ == '__main__':
    table = Table('dm', group_id='M3238')
    table.reload()
    table.mark_tasks('M3238', 'Бондарев Федор Алексеевич', [('Неделя 2', '31')])

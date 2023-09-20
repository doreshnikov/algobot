from dataclasses import dataclass, field
from pathlib import Path

import json5

from algobot.config import sheets_config
from algobot.drivers.google import sheets_driver


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


class InvalidMappingError(Exception):
    def __init__(self, group_ids: list[str], mapped_names: set[str]):
        self.group_ids = group_ids
        self.mapped_names = mapped_names
        super().__init__(
            f'Groups {group_ids} have inconsistent sheet name mapping: {mapped_names}'
        )


@dataclass
class Mapping:
    students: dict[tuple[str, str], int] = field(default_factory=dict)
    weeks: dict[str, int] = field(default_factory=dict)
    tasks: dict[tuple[str, str], int] = field(default_factory=dict)


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
        group_mapping = self.template['group_sheet_mapping']
        if group_mapping:
            group_names = {group_mapping.get(group_id) for group_id in self.group_ids}
            if len(group_names) > 1:
                raise InvalidMappingError(self.group_ids, group_names)
            self.group_name = group_names.pop()
        self.table = self.spreadsheet.worksheet(self.group_name)
        self.mapping = Mapping()

    @staticmethod
    def a1r1_notation(row: int, column: int):
        alpha = ord('Z') - ord('A') + 1
        column_name = ''
        while column > 0:
            column_name += chr(ord('A') + column % alpha)
            column //= alpha
        return f'${column_name[::-1]}${row}'

    @property
    def index_columns(self) -> int:
        return self.template['index_columns']

    @property
    def header_rows(self) -> int:
        return self.template['header_rows']

    def reload(self):
        header = self.table.get_all_records(
            f'{Table.a1r1_notation(1, 1)}:'
            f'{Table.a1r1_notation(self.header_rows, self.table.col_count)}'
        )
        index = self.table.get_all_records(
            f'{Table.a1r1_notation(1, 1)}:'
            f'{Table.a1r1_notation(self.table.row_count, self.index_columns)}'
        )
        print(header)
        print(index)

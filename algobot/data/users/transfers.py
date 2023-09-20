from peewee import Model, ForeignKeyField

from algobot.drivers.sqlite import database
from .students import Student
from ..courses.courses import Course


class Transfer(Model):
    course_ref = ForeignKeyField(Course)
    student_ref = ForeignKeyField(Student)

    class Meta:
        primary_key = False
        database = database


Transfer.create_table(safe=True)


class Transfers:
    @staticmethod
    def list_external_course_students(
        course: str, group_id: str
    ) -> list[tuple[str, str]]:
        students = (
            Transfer.select()
            .join(Student)
            .where((Transfer.course == course) & (Transfer.transfer_group == group_id))
        )
        return students

from peewee import Model, AutoField, CharField, ForeignKeyField

from .. import database


class Course(Model):
    id_ = AutoField(primary_key=True)
    course = CharField()
    group_id = CharField()

    class Meta:
        database = database


Course.create_table(safe=True)


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

from peewee import Model, IntegerField, CharField, ForeignKeyField

from algobot.drivers.sqlite import database
from .students import Student


class User(Model):
    tg_id = IntegerField(primary_key=True)
    tg_username = CharField(unique=True, null=True)
    tg_name = CharField()
    student_ref = ForeignKeyField(Student)
    selected_course = CharField(null=True)

    class Meta:
        database = database
        table_name = 'user'


User.create_table(safe=True)


class Users:
    @staticmethod
    def get_user(tg_id: int) -> dict | None:
        students = (
            User.select(User, Student)
            .join(Student)
            .limit(1)
            .where(User.tg_id == tg_id)
            .dicts()
        )
        return students[0] if len(students) > 0 else None

    @staticmethod
    def get_user_by_name(group_id: int, student_name: str) -> dict | None:
        students = (
            User.select(User, Student)
            .join(Student)
            .limit(1)
            .where(
                (Student.group_id == group_id) & (Student.student_name == student_name)
            )
            .dicts()
        )
        return students[0] if len(students) > 0 else None

    @staticmethod
    def update_tg_name(tg_id: int, tg_name: str):
        with database.atomic():
            if user := User.get(User.tg_id == tg_id):
                user.tg_name = tg_name
                user.save()

    @staticmethod
    def insert_user(
        tg_id: int, tg_username: str, tg_name: str, group_id: str, student_name: str
    ):
        with database.atomic():
            student = Student.get(
                (Student.group_id == group_id) & (Student.student_name == student_name)
            )
            User.insert(
                tg_id=tg_id,
                tg_username=tg_username,
                tg_name=tg_name,
                student_ref=student.id_,
            ).execute()
            database.cursor().execute(f'PRAGMA foreign_key_check(user)')

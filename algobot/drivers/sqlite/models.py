from peewee import Model, AutoField, CharField, ForeignKeyField, IntegerField

from algobot.drivers.sqlite import database


class Student(Model):
    id_ = AutoField(primary_key=True)
    group_id = CharField()
    student_name = CharField()

    class Meta:
        database = database
        table_name = 'student'
        indexes = ((('group_id', 'student_name'), True),)


class Course(Model):
    id_ = AutoField(primary_key=True)
    course = CharField()
    group_id = CharField()

    class Meta:
        database = database
        table_name = 'course'


class User(Model):
    tg_id = IntegerField(primary_key=True)
    tg_username = CharField(unique=True, null=True)
    tg_name = CharField()
    student_ref = ForeignKeyField(Student)
    selected_course = CharField(null=True)

    class Meta:
        database = database
        table_name = 'user'


class Transfer(Model):
    course_ref = ForeignKeyField(Course)
    student_ref = ForeignKeyField(Student)

    class Meta:
        primary_key = False
        database = database


database.create_tables([Student, Course, User, Transfer], safe=True)

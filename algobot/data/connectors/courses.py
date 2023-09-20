from algobot.drivers.sqlite import database
from algobot.drivers.sqlite.models import Course
from algobot.config import sheets_config


class Courses:
    @staticmethod
    def list_courses() -> list[dict]:
        return Course.select().dicts()

    @staticmethod
    def load_from_config(clear: bool = False):
        with database.atomic():
            if clear:
                Course.delete().execute()
            for course_config in sheets_config['courses']:
                course = course_config['course']
                for group in course_config['groups']:
                    Course.get_or_create(course=course, group_id=group)


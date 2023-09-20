from algobot.config import sheets_config


def get_default_course(group: str) -> str:
    for course_config in sheets_config['courses']:
        course = course_config['course']
        if group in course_config['groups']:
            return course

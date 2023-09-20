from algobot.drivers.sqlite.models import Student, Transfer


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

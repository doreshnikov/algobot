from algobot.drivers.sqlite.models import Student


class Students:
    @staticmethod
    def list_groups() -> list[str]:
        rows = (
            Student.select(Student.group_id)
            .order_by(Student.group_id)
            .distinct()
            .dicts()
        )
        return [row['group_id'] for row in rows]

    @staticmethod
    def list_group_students(group_id: str) -> list[str]:
        rows = (
            Student.select(Student.student_name)
            .order_by(Student.student_name)
            .where(Student.group_id == group_id)
            .dicts()
        )
        return [row['student_name'] for row in rows]

    @staticmethod
    def get_student_by_name(group_id: str, student_name: str) -> dict | None:
        rows = (
            Student.select()
            .limit(1)
            .where(
                (Student.group_id == group_id) & (Student.student_name == student_name)
            )
            .dicts()
        )
        return rows[0] if len(rows) > 0 else None

    @staticmethod
    def register_student(group_id: str, student_name: str):
        Student.insert(group_id=group_id, student_name=student_name).execute()

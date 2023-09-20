def user_reference(tg_id: int, tg_username: str | None, tg_name: str):
    if tg_username:
        return f'@{tg_username}'
    return f'[{tg_name}](tg://user?id={tg_id})'


def full_student_info(student_name: str, group_id: str) -> object:
    return f'{student_name} [Группа {group_id}]'

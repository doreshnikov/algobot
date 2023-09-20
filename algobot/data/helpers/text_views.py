def user_reference(tg_id: int, tg_username: str | None, tg_name: str) -> str:
    if tg_username:
        return f'@{tg_username}'
    return f'[{tg_name}](tg://user?id={tg_id})'


def full_student_info(student_name: str, group_id: str) -> str:
    return f'{student_name} [Группа {group_id}]'


def full_name(first_name: str, last_name: str) -> str:
    return f'{first_name} {last_name}'

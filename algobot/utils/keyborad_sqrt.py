from aiogram.utils.keyboard import InlineKeyboardBuilder


def reshape(builder: InlineKeyboardBuilder, items: int):
    rows = int(items**0.5)
    item_count = [items // rows for _ in range(rows)]
    if (remainder := items % rows) != 0:
        item_count.append(remainder)
    builder.adjust(*item_count)

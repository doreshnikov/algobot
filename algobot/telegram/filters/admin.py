from telebot.custom_filters import SimpleCustomFilter
from telebot.types import Message

from algobot.common.config import Config


class AdminFilter(SimpleCustomFilter):
    key = 'admin'

    # noinspection PyMethodOverriding
    @staticmethod
    def check(message: Message) -> bool:
        return message.from_user.id == Config().telegram['admin_id']

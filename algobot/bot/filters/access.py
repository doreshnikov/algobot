from aiogram import F

from algobot.config import telegram_config

IsAdmin = F.from_user.id == telegram_config['admin_id']
IsTeacher = F.from_user.id.in_(telegram_config['teacher_ids'])

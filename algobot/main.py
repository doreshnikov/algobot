import sys
import json5
import asyncio
import logging

from aiogram import Bot, Dispatcher

from algobot.bot import dispatcher

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)


async def main():
    with open('config/config.json5') as config_stream:
        config = json5.load(config_stream)
    token = config['telegram']['token']

    bot = Bot(token, parse_mode='HTML')
    await dispatcher.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())

import asyncio
import logging
import sys

import json5
from aiogram import Bot

from algobot.bot import dispatcher

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)


async def main():
    with open('config/config.json5') as config_stream:
        config = json5.load(config_stream)
    token = config['telegram']['token']

    bot = Bot(token)
    await dispatcher.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())

from .logsetup import root_logger

import asyncio

import json5
from aiogram import Bot

from algobot.bot import dispatcher


async def main():
    with open('config/config.json5') as config_stream:
        config = json5.load(config_stream)
    token = config['telegram']['token']

    bot = Bot(token)
    root_logger.info('Starting up...')
    await dispatcher.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())

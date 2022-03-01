import logging

from algobot.db.registry import SheetsRegistry
from algobot.db.mapping import Mapping

from algobot.telegram.bot import AlgoBot

handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - [%(levelname)s]   %(message)s')
handler.setFormatter(formatter)
logging.getLogger().setLevel(logging.DEBUG)
logging.getLogger().addHandler(handler)

logger = logging.getLogger(__name__)
logger.info('Creating driver...')
driver = SheetsRegistry()
logger.info('Connecting mapping...')
mapping = Mapping()

logger.info('Starting bot...')
algobot = AlgoBot(driver, mapping)
algobot.run()

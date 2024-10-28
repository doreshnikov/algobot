import logging
import sys


def setup_logging():
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)


setup_logging()
root_logger = logging.getLogger('__main__')

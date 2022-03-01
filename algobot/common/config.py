import os
import yaml
from typing import Any

import logging

from algobot.misc.singleton import Singleton

logger = logging.getLogger(__name__)


class KeyNotFoundError(LookupError):
    def __init__(self, root_name: str, key_name: str):
        self.root_name = root_name
        self.key_name = key_name
        message = f'Key \'{key_name}\' not present in config of \'{root_name}\''
        logger.error(message)
        super().__init__(message)


class Config(metaclass=Singleton):
    @staticmethod
    def _validate(config: dict, root: str, keys: list[str]) -> Any:
        for key in keys:
            if key not in config[root]:
                raise KeyNotFoundError
        return config[root]

    def __init__(self):
        logger.info('Parsing config...')
        conf_file = os.environ['conf']
        with open(conf_file) as conf:
            config = yaml.safe_load(conf)

        self.sheets = Config._validate(config, 'sheets', ['credentials_file', 'sheet_id'])
        self.telegram = Config._validate(config, 'telegram', ['token'])
        self.local = Config._validate(config, 'local', ['user_db_file'])
        logger.info('Config saved')

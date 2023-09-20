import os
import pathlib

from algobot.config import sheets_config

credentials_file = sheets_config
sheets_driver = None
if credentials_file.exists() and not os.getenv('DEBUG'):
    sheets_driver = SheetsDriver(str(credentials_file))

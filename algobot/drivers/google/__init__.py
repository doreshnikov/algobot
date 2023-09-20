from pathlib import Path

from algobot.config import sheets_config
from .sheets import SheetsDriver

credentials_file = sheets_config['credentials_file']
credentials_path = Path(credentials_file)
sheets_driver = None
if credentials_path.is_file():
    sheets_driver = SheetsDriver(credentials_file)

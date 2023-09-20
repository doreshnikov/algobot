import pathlib

import json5

config_file = pathlib.Path() / 'config' / 'config.json5'
if not config_file.is_file():
    raise FileNotFoundError(
        'You should place configuration file in <project>/config/config.json5'
    )

with open(config_file) as config_stream:
    config_data = json5.load(config_stream)

local_config = config_data['local']
telegram_config = config_data['telegram']
sheets_config = config_data['sheets']

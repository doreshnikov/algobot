from peewee import SqliteDatabase

from algobot.config import local_config

database = SqliteDatabase(
    local_config['sqlite_source'],
    pragmas={
        'journal_mode': 'wal',
        'foreign_keys': 1,
        'ignore_check_constrains': 0,
    },
)
database.connect()

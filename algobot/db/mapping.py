from __future__ import annotations

from typing import Any
import logging

from peewee import *

from algobot.common.config import Config
from algobot.common.feedback import RequestResult, RequestSuccess, RequestFail


logger = logging.getLogger(__name__)


class Mapping:
    def _init_user_model(self):
        logger.info('Creating User model')
        class User(Model):
            tg_id = IntegerField(null=False, primary_key=True)
            tg_ref = CharField(max_length=100, null=True, unique=True)
            group_id = CharField(max_length=6, null=False)
            student_name = CharField(null=False)

            class Meta:
                database = self.db
                table_name = 'user'
                indexes = (
                    (('group_id', 'student_name'), True),
                )

        self.db.create_tables([User])
        logger.info('Model created/connected')
        return User

    def __init__(self):
        db_file = Config().local['user_db_file']
        self.db = SqliteDatabase(db_file)
        self.db.connect()
        self.U = self._init_user_model()
        logger.info('Mapper created')

    # Use Any since it's unknown what type doest query return TODO fix later
    def query_by_id(self, tg_id: int) -> Any | RequestResult:
        logger.info(f'Query user by id {tg_id}')
        return self.U.get_or_none(self.U.tg_id == tg_id)

    def query_by_name(self, group_id: str, student_name: str) -> Any | RequestResult:
        logger.info(f'Query user by group/name {group_id}/{student_name}')
        return self.U.get_or_none(self.U.group_id == group_id and self.U.student_name == student_name)

    def register(self, tg_id: int, tg_ref: str, group_id: str, student_name: str) -> RequestResult:
        logger.info(f'Register user by id {tg_id}, ref {tg_ref} and creds {group_id}/{student_name}')
        with self.db.atomic() as transaction:
            try:
                student = self.query_by_name(group_id, student_name)
                if student:
                    return RequestFail(
                        'You have been already registered' if student.tg_id == tg_id
                        else f'This name is already taken by \'@{student.tg_ref}\''
                    )
                user = self.query_by_id(tg_id)
                if not user:
                    self.U \
                        .insert(tg_id=tg_id, tg_ref=tg_ref, group_id=group_id, student_name=student_name) \
                        .execute()
                else:
                    user.tg_ref = tg_ref
                    user.group_id, user.student_name = group_id, student_name
                    user.save()
                return RequestSuccess()
            except DatabaseError:
                transaction.rollback()
                return RequestFail('DB transaction failed, try again')

    def unregister(self, tg_id: int) -> RequestResult:
        logger.info(f'Unregister user by id {tg_id}')
        with self.db.atomic() as transaction:
            try:
                user = self.query_by_id(tg_id)
                if not user:
                    return RequestFail('You are not registered as anyone yet')
                user.delete_instance()
            except DatabaseError:
                transaction.rollback()
                return RequestFail('DB transaction failed, try again')

import ydb
from typing import List

from config import Config
from user_orm import UserORM
from group_orm import GroupORM
from abstract_base import (
    AbstractBase,
    UserDoesntExistInDB,
)


class Database(AbstractBase):

    def __init__(self):
        self.driver = ydb.Driver(
            endpoint=Config.YDB_ENDPOINT,
            database=Config.YDB_DATABASE,
            credentials=ydb.construct_credentials_from_environ(),
        )
        self.driver.wait(fail_fast=True, timeout=5)
        self.pool = ydb.SessionPool(self.driver)

    def __del__(self):
        self.pool.stop()
        self.driver.stop()

    def get_user_info(self, telegram_id: str) -> UserORM:
        def select(session):
            return session.transaction().execute(
                """
                    SELECT
                        `id`,
                        `telegram_id`,
                        `first_name`,
                        `last_name`,
                    FROM `users`
                    WHERE `telegram_id` == "{}";
                """.format(
                    telegram_id
                ),
                commit_tx=True,
                settings=ydb.BaseRequestSettings().with_timeout(3).with_operation_timeout(2)
            )

        result = self.pool.retry_operation_sync(select)

        if len(result[0].rows) == 0:
            raise UserDoesntExistInDB

        return UserORM(
            id=result[0].rows[0].id,
            telegram_id=result[0].rows[0].telegram_id.decode('utf-8'),
            first_name=result[0].rows[0].first_name.decode('utf-8'),
            last_name=result[0].rows[0].last_name.decode('utf-8'),
        )

    def create_user(self, telegram_id: str, first_name: str, last_name: str) -> None:
        def upsert(session):
            return session.transaction().execute(
                """
                    INSERT INTO `users` (`telegram_id`, `first_name`, `last_name`) 
                    VALUES ("{}", "{}", "{}")
                """.format(
                    telegram_id,
                    first_name,
                    last_name
                ),
                commit_tx=True,
                settings=ydb.BaseRequestSettings().with_timeout(3).with_operation_timeout(2)
            )

        self.pool.retry_operation_sync(upsert)

    def get_group_list(self, user: UserORM) -> List[GroupORM]:
        def select(session):
            return session.transaction().execute(
                """
                    SELECT
                        `g`.`id` AS `id`,
                        `created_at`,
                        `name`,
                    FROM `group_members` AS `gm`
                    LEFT JOIN `groups` AS `g`
                    ON `gm`.`group_id` == `g`.`id`
                    WHERE `gm`.`user_id` == {};
                """.format(
                    user.id
                ),
                commit_tx=True,
                settings=ydb.BaseRequestSettings().with_timeout(3).with_operation_timeout(2)
            )

        result = self.pool.retry_operation_sync(select)
        return [GroupORM(id=e.id, created_at=e.created_at, name=e.name.decode('utf-8')) for e in result[0].rows]

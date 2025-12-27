import ydb
from typing import List
import datetime

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
            telegram_id=result[0].rows[0].telegram_id,
            first_name=result[0].rows[0].first_name,
            last_name=result[0].rows[0].last_name,
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
                        `created_by`,
                        `name`,
                        `count`,
                        Digest::Md5Hex(CAST(`g`.`id` AS String) || `created_at` || CAST(`created_by` AS String)) AS `token`,
                    FROM `group_members` AS `gm`
                    LEFT JOIN `groups` AS `g`
                    ON `gm`.`group_id` == `g`.`id`
                    LEFT JOIN (
                        SELECT
                            `group_id`,
                            COUNT(*) AS `count`,
                        FROM `group_members`
                        GROUP BY `group_id`
                    ) AS `gc`
                    ON `gm`.`group_id` == `gc`.`group_id`
                    WHERE `gm`.`user_id` == {};
                """.format(
                    user.id
                ),
                commit_tx=True,
                settings=ydb.BaseRequestSettings().with_timeout(3).with_operation_timeout(2)
            )

        result = self.pool.retry_operation_sync(select)
        return [
            GroupORM(
                id=e.id,
                created_at=e.created_at,
                name=e.name,
                count=e.count,
                created_by=e.created_by,
                token=e.token.decode('utf-8')
            ) for e in result[0].rows
        ]

    def create_group(self, user: UserORM, name: str) -> None:
        def insert_group(session):
            return session.transaction().execute(
                """
                    INSERT INTO `groups` (`created_at`, `created_by`, `name`) 
                    VALUES ("{}", {}, "{}")
                    RETURNING *
                """.format(
                    datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    user.id,
                    name
                ),
                commit_tx=True,
                settings=ydb.BaseRequestSettings().with_timeout(3).with_operation_timeout(2)
            )

        def insert_member(session):
            return session.transaction().execute(
                """
                    INSERT INTO `group_members` (`group_id`, `user_id`) 
                    VALUES ({}, {})
                """.format(
                    result[0].rows[0].id,
                    user.id
                ),
                commit_tx=True,
                settings=ydb.BaseRequestSettings().with_timeout(3).with_operation_timeout(2)
            )

        result = self.pool.retry_operation_sync(insert_group)
        self.pool.retry_operation_sync(insert_member)

    def change_group_name(self, group_id: int, name: str, created_at: str, created_by: int) -> None:
        def upsert(session):
            return session.transaction().execute(
                """
                    UPSERT INTO `groups` (`id`, `name`, `created_at`, `created_by`) 
                    VALUES ({}, "{}", "{}", {})
                """.format(
                    group_id,
                    name,
                    created_at,
                    created_by
                ),
                commit_tx=True,
                settings=ydb.BaseRequestSettings().with_timeout(3).with_operation_timeout(2)
            )

        self.pool.retry_operation_sync(upsert)

    def get_group_member_list(self, group_id: int) -> List[UserORM]:
        def select(session):
            return session.transaction().execute(
                """
                    SELECT
                        `u`.`id` AS `id`,
                        `telegram_id`,
                        `first_name`,
                        `last_name`,
                    FROM `group_members` AS `gm`
                    LEFT JOIN `users` AS `u`
                    ON `gm`.`user_id` == `u`.`id`
                    WHERE `gm`.`group_id` == {};
                """.format(
                    group_id
                ),
                commit_tx=True,
                settings=ydb.BaseRequestSettings().with_timeout(3).with_operation_timeout(2)
            )

        result = self.pool.retry_operation_sync(select)
        return [
            UserORM(id=e.id, telegram_id=e.telegram_id, first_name=e.first_name, last_name=e.last_name)
            for e in result[0].rows
        ]

    def join_to_group(self, user: UserORM, group_token: str) -> None:
        def insert_member(session):
            return session.transaction().execute(
                """
                    INSERT INTO `group_members`
                    SELECT
                        `id` AS `group_id`,
                        {} AS `user_id`,
                    FROM `groups`
                    WHERE 
                        Digest::Md5Hex(CAST(`id` AS String) || `created_at` || CAST(`created_by` AS String)) == "{}"
                """.format(
                    user.id,
                    group_token
                ),
                commit_tx=True,
                settings=ydb.BaseRequestSettings().with_timeout(3).with_operation_timeout(2)
            )

        self.pool.retry_operation_sync(insert_member)

    def leave_group(self, user: UserORM, group_id: int) -> None:
        def delete_member(session):
            return session.transaction().execute(
                """
                    DELETE FROM `group_members`
                    WHERE
                        `group_id` == {} AND
                        `user_id` == {}
                """.format(
                    group_id,
                    user.id,
                ),
                commit_tx=True,
                settings=ydb.BaseRequestSettings().with_timeout(3).with_operation_timeout(2)
            )

        self.pool.retry_operation_sync(delete_member)

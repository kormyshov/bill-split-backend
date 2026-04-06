import ydb
from typing import List
import datetime

from config import Config
from user_orm import UserORM
from group_orm import GroupORM
from expense_orm import ExpenseORM
from debt_orm import DebtORM
from balance_orm import BalanceORM
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
                        `expired_date` ?? "1900-01-01" AS `expired_date`,
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
            expired_date=result[0].rows[0].expired_date,
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
            UserORM(
                id=e.id,
                telegram_id=e.telegram_id,
                first_name=e.first_name,
                last_name=e.last_name,
                expired_date='1900-01-01',
            ) for e in result[0].rows
        ]

    def join_to_group(self, user: UserORM, group_token: str) -> None:
        def insert_member(session):
            return session.transaction().execute(
                """
                    $group_id = 
                    SELECT
                        `id`,
                    FROM `groups`
                    WHERE
                        Digest::Md5Hex(CAST(`id` AS String) || `created_at` || CAST(`created_by` AS String)) == "{}"
                    ;

                    DELETE FROM `group_members`
                    WHERE
                        `group_id` == $group_id AND
                        `user_id` == {}
                    ;

                    INSERT INTO `group_members`
                    SELECT
                        $group_id  ?? 1 AS `group_id`,
                        {} AS `user_id`
                    ;
                """.format(
                    group_token,
                    user.id,
                    user.id,
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

    def get_group_expense_list(self, user: UserORM, group_id: int) -> List[ExpenseORM]:
        def select(session):
            return session.transaction().execute(
                """
                    $input =
                    SELECT
                        `id`,
                        `name`,
                        `created_at`,
                        `amount`,
                        `currency`,
                        `paid_by`,
                    FROM `expenses`
                    WHERE `group_id` == {}
                    ;

                    $a =
                    SELECT
                        `e`.`id` AS `id`,
                        `e`.`name` AS `name`,
                        `e`.`created_at` AS `created_at`,
                        `e`.`amount` AS `amount`,
                        `c`.`symbol` AS `currency_symbol`,
                        `u`.`first_name` || " " || `u`.`last_name` AS `first_and_last_name`,
                        `e`.`paid_by` AS `paid_by`,
                    FROM $input AS `e`
                    LEFT JOIN `currencies` AS `c`
                    ON `e`.`currency` == `c`.`id`
                    LEFT JOIN `users` AS `u`
                    ON `e`.`paid_by` == `u`.`id`
                    ;

                    $b =
                    SELECT
                        `id`,
                        SOME(`a`.`amount`) * IF (SOME(`a`.`paid_by`) == {}, 1, 0) -
                        (SUM_IF(`d`.`amount`, `d`.`user_id` == {}) ?? 0) AS `debt_amount`,
                    FROM `debts` AS `d`
                    INNER JOIN $a AS `a`
                    ON `d`.`expense_id` == `a`.`id`
                    GROUP BY `a`.`id` AS `id`
                    ;

                    SELECT
                        `debt_amount` ?? 0 AS `debt_amount`,
                        `a`.* WITHOUT `a`.`paid_by`,
                    FROM $a AS `a`
                    LEFT JOIN $b AS `b`
                    USING (`id`)
                    ;
                """.format(
                    group_id,
                    user.id,
                    user.id
                ),
                commit_tx=True,
                settings=ydb.BaseRequestSettings().with_timeout(3).with_operation_timeout(2)
            )

        result = self.pool.retry_operation_sync(select)
        return [
            ExpenseORM(
                id=e.id,
                name=e.name,
                created_at=e.created_at,
                first_and_last_name=e.first_and_last_name.decode('utf-8'),
                amount=e.amount,
                currency_symbol=e.currency_symbol,
                debt_amount=e.debt_amount,
            )
            for e in result[0].rows
        ]

    def get_expense_debt_list(self, expense_id: int) -> List[DebtORM]:
        def select(session):
            return session.transaction().execute(
                """
                    SELECT
                        `d`.`id` AS `id`,
                        `e`.`name` AS `expense_name`,
                        `e`.`created_at` AS `created_at`,
                        `e`.`amount` AS `total_amount`,
                        `c`.`symbol` AS `currency_symbol`,
                        `u`.`first_name` || " " || `u`.`last_name` AS `paid_by_first_and_last_name`,
                        `d`.`amount` AS `debt_amount`,
                        `uu`.`first_name` || " " || `uu`.`last_name` AS `first_and_last_name`,
                    FROM `expenses` AS `e`
                    LEFT JOIN `currencies` AS `c`
                    ON `e`.`currency` == `c`.`id`
                    LEFT JOIN `users` AS `u`
                    ON `e`.`paid_by` == `u`.`id`
                    LEFT JOIN `debts` AS `d`
                    ON `e`.`id` == `d`.`expense_id`
                    LEFT JOIN `users` AS `uu`
                    ON `d`.`user_id` == `uu`.`id`
                    WHERE `e`.`id` == {};
                """.format(
                    expense_id
                ),
                commit_tx=True,
                settings=ydb.BaseRequestSettings().with_timeout(3).with_operation_timeout(2)
            )

        result = self.pool.retry_operation_sync(select)
        return [
            DebtORM(
                id=e.id,
                expense_name=e.expense_name,
                created_at=e.created_at,
                total_amount=e.total_amount,
                currency_symbol=e.currency_symbol,
                paid_by_first_and_last_name=e.paid_by_first_and_last_name.decode('utf-8'),
                debt_amount=e.debt_amount,
                first_and_last_name=e.first_and_last_name.decode('utf-8')
            )
            for e in result[0].rows
        ]

    def create_expense(self, user: UserORM, group_id: int, name: str, amount: int, currency_id: int) -> int:
        def insert_expense(session):
            return session.transaction().execute(
                """
                    INSERT INTO `expenses` (`created_at`, `group_id`, `name`, `paid_by`, `amount`, `currency`) 
                    VALUES ("{}", {}, "{}", {}, {}, {})
                    RETURNING *
                """.format(
                    datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    group_id,
                    name,
                    user.id,
                    amount,
                    currency_id
                ),
                commit_tx=True,
                settings=ydb.BaseRequestSettings().with_timeout(3).with_operation_timeout(2)
            )

        result = self.pool.retry_operation_sync(insert_expense)
        return result[0].rows[0].id

    def create_debt(self, expense_id: int, user_id: int, amount: int) -> None:
        def upsert(session):
            return session.transaction().execute(
                """
                    INSERT INTO `debts` (`expense_id`, `user_id`, `amount`) 
                    VALUES ({}, {}, {})
                """.format(
                    expense_id,
                    user_id,
                    amount
                ),
                commit_tx=True,
                settings=ydb.BaseRequestSettings().with_timeout(3).with_operation_timeout(2)
            )

        self.pool.retry_operation_sync(upsert)

    def delete_expense(self, expense_id: int) -> None:
        def delete(session):
            return session.transaction().execute(
                """
                    DELETE FROM `expenses`
                    WHERE `id` == {}
                    ;
                    DELETE FROM `debts`
                    WHERE `expense_id` == {}
                    ;
                """.format(
                    expense_id,
                    expense_id,
                ),
                commit_tx=True,
                settings=ydb.BaseRequestSettings().with_timeout(3).with_operation_timeout(2)
            )

        self.pool.retry_operation_sync(delete)

    def get_group_balance_list(self, user: UserORM, group_id: int) -> List[BalanceORM]:
        def select(session):
            return session.transaction().execute(
                """
                    $input =
                    SELECT
                        `id`,
                        `currency`,
                        `paid_by`,
                    FROM `expenses`
                    WHERE `group_id` == {}
                    ;

                    $from_ = 
                    SELECT
                        *
                    FROM $input
                    WHERE `paid_by` == {}
                    ;

                    $from =
                    SELECT
                        `e`.`currency` AS `currency`,
                        `d`.`user_id` AS `user_id`,
                        `d`.`amount` AS `amount`,
                    FROM $from_ AS `e`
                    LEFT JOIN `debts` AS `d`
                    ON `e`.`id` == `d`.`expense_id`
                    WHERE `user_id` != {}
                    ;

                    $to_ =
                    SELECT
                        *
                    FROM $input
                    WHERE `paid_by` != {}
                    ;

                    $to =
                    SELECT
                        `e`.`currency` AS `currency`,
                        `e`.`paid_by` AS `user_id`,
                        -`d`.`amount` AS `amount`,
                    FROM $to_ AS `e`
                    INNER JOIN `debts` AS `d`
                    ON `e`.`id` == `d`.`expense_id`
                    WHERE `user_id` == {}
                    ;

                    $total =
                    SELECT
                        `user_id`,
                        `currency`,
                        SUM(`amount`) AS `amount`,
                    FROM (
                        SELECT * FROM $from
                        UNION ALL
                        SELECT * FROM $to
                    )
                    GROUP BY `user_id`, `currency`
                    HAVING SUM(`amount`) != 0
                    ;

                    SELECT
                        `t`.`user_id` AS `user_id`,
                        `t`.`currency` AS `currency`,
                        `t`.`amount` AS `amount`,
                        `c`.`symbol` AS `currency_symbol`,
                        `u`.`first_name` || " " || `u`.`last_name` AS `first_and_last_name`,
                    FROM $total AS `t`
                    LEFT JOIN `currencies` AS `c`
                    ON `t`.`currency` == `c`.`id`
                    LEFT JOIN `users` AS `u`
                    ON `t`.`user_id` == `u`.`id`
                    ;
                """.format(
                    group_id,
                    user.id,
                    user.id,
                    user.id,
                    user.id
                ),
                commit_tx=True,
                settings=ydb.BaseRequestSettings().with_timeout(3).with_operation_timeout(2)
            )

        result = self.pool.retry_operation_sync(select)
        return [
            BalanceORM(
                user_id=e.user_id,
                currency=e.currency,
                amount=e.amount,
                currency_symbol=e.currency_symbol,
                first_and_last_name=e.first_and_last_name.decode('utf-8'),
            )
            for e in result[0].rows
        ]

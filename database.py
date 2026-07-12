import ydb
import ydb.iam
from typing import List
import datetime

from config import Config
from expense_draft import ExpenseDraft
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
            credentials=ydb.iam.MetadataUrlCredentials()
        )
        self.driver.wait(fail_fast=True, timeout=5)
        self.pool = ydb.SessionPool(self.driver)

    def __del__(self):
        self.pool.stop()
        self.driver.stop()

    def get_user_info(self, telegram_id: str) -> UserORM:
        def select(session):
            query = ydb.DataQuery(
                """
                    DECLARE $telegram_id AS Utf8;
                    SELECT
                        `id`,
                        `telegram_id`,
                        `first_name`,
                        `last_name`,
                        `expired_date` ?? '1900-01-01' AS `expired_date`,
                    FROM `users`
                    WHERE `telegram_id` == $telegram_id;
                """,
                {"$telegram_id": ydb.PrimitiveType.Utf8}
            )
            return session.transaction().execute(
                query,
                {"$telegram_id": telegram_id},
                commit_tx=True,
                settings=ydb.BaseRequestSettings().with_timeout(3).with_operation_timeout(2),
            )

        result = self.pool.retry_operation_sync(select)

        if len(result[0].rows) == 0:
            raise UserDoesntExistInDB

        return UserORM(
            id=result[0].rows[0].id,
            telegram_id=result[0].rows[0].telegram_id,
            first_name=result[0].rows[0].first_name,
            last_name=result[0].rows[0].last_name,
            expired_date=result[0].rows[0].expired_date.decode('utf-8'),
        )

    def create_user(self, telegram_id: str, first_name: str, last_name: str) -> None:
        def upsert(session):
            query = ydb.DataQuery(
                """
                    DECLARE $telegram_id AS Utf8;
                    DECLARE $first_name AS Utf8;
                    DECLARE $last_name AS Utf8;
                    INSERT INTO `users` (`telegram_id`, `first_name`, `last_name`)
                    VALUES ($telegram_id, $first_name, $last_name)
                """,
                {"$telegram_id": ydb.PrimitiveType.Utf8, "$first_name": ydb.PrimitiveType.Utf8, "$last_name": ydb.PrimitiveType.Utf8}
            )
            return session.transaction().execute(
                query,
                {"$telegram_id": telegram_id, "$first_name": first_name, "$last_name": last_name},
                commit_tx=True,
                settings=ydb.BaseRequestSettings().with_timeout(3).with_operation_timeout(2)
            )

        self.pool.retry_operation_sync(upsert)

    def get_group_list(self, user: UserORM) -> List[GroupORM]:
        def select(session):
            query = ydb.DataQuery(
                """
                    DECLARE $user_id AS Int64;
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
                    WHERE `gm`.`user_id` == $user_id;
                """,
                {"$user_id": ydb.PrimitiveType.Int64}
            )
            return session.transaction().execute(
                query,
                {"$user_id": user.id},
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
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        def create(session):
            tx = session.transaction()
            result = tx.execute(
                ydb.DataQuery(
                    """
                        DECLARE $created_at AS Utf8;
                        DECLARE $created_by AS Int64;
                        DECLARE $name AS Utf8;
                        INSERT INTO `groups` (`created_at`, `created_by`, `name`)
                        VALUES ($created_at, $created_by, $name)
                        RETURNING *
                    """,
                    {"$created_at": ydb.PrimitiveType.Utf8, "$created_by": ydb.PrimitiveType.Int64, "$name": ydb.PrimitiveType.Utf8}
                ),
                {"$created_at": now, "$created_by": user.id, "$name": name},
                commit_tx=False,
                settings=ydb.BaseRequestSettings().with_timeout(3).with_operation_timeout(2)
            )
            tx.execute(
                ydb.DataQuery(
                    """
                        DECLARE $group_id AS Int64;
                        DECLARE $user_id AS Int64;
                        INSERT INTO `group_members` (`group_id`, `user_id`)
                        VALUES ($group_id, $user_id)
                    """,
                    {"$group_id": ydb.PrimitiveType.Int64, "$user_id": ydb.PrimitiveType.Int64}
                ),
                {"$group_id": result[0].rows[0].id, "$user_id": user.id},
                commit_tx=True,
                settings=ydb.BaseRequestSettings().with_timeout(3).with_operation_timeout(2)
            )

        self.pool.retry_operation_sync(create)

    def change_group_name(self, group_id: int, name: str, created_at: str, created_by: int) -> None:
        def upsert(session):
            query = ydb.DataQuery(
                """
                    DECLARE $group_id AS Int64;
                    DECLARE $name AS Utf8;
                    DECLARE $created_at AS Utf8;
                    DECLARE $created_by AS Int64;
                    UPSERT INTO `groups` (`id`, `name`, `created_at`, `created_by`)
                    VALUES ($group_id, $name, $created_at, $created_by)
                """,
                {"$group_id": ydb.PrimitiveType.Int64, "$name": ydb.PrimitiveType.Utf8, "$created_at": ydb.PrimitiveType.Utf8, "$created_by": ydb.PrimitiveType.Int64}
            )
            return session.transaction().execute(
                query,
                {"$group_id": group_id, "$name": name, "$created_at": created_at, "$created_by": created_by},
                commit_tx=True,
                settings=ydb.BaseRequestSettings().with_timeout(3).with_operation_timeout(2)
            )

        self.pool.retry_operation_sync(upsert)

    def get_group_member_list(self, group_id: int) -> List[UserORM]:
        def select(session):
            query = ydb.DataQuery(
                """
                    DECLARE $group_id AS Int64;
                    SELECT
                        `u`.`id` AS `id`,
                        `telegram_id`,
                        `first_name`,
                        `last_name`,
                    FROM `group_members` AS `gm`
                    LEFT JOIN `users` AS `u`
                    ON `gm`.`user_id` == `u`.`id`
                    WHERE `gm`.`group_id` == $group_id;
                """,
                {"$group_id": ydb.PrimitiveType.Int64}
            )
            return session.transaction().execute(
                query,
                {"$group_id": group_id},
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
            query = ydb.DataQuery(
                """
                    DECLARE $group_token AS Utf8;
                    DECLARE $user_id AS Int64;
                    $group_id =
                    SELECT
                        `id`,
                    FROM `groups`
                    WHERE
                        Digest::Md5Hex(CAST(`id` AS String) || `created_at` || CAST(`created_by` AS String)) == $group_token
                    ;

                    DELETE FROM `group_members`
                    WHERE
                        `group_id` == $group_id AND
                        `user_id` == $user_id
                    ;

                    INSERT INTO `group_members`
                    SELECT
                        $group_id  ?? 1 AS `group_id`,
                        $user_id AS `user_id`
                    ;
                """,
                {"$group_token": ydb.PrimitiveType.Utf8, "$user_id": ydb.PrimitiveType.Int64}
            )
            return session.transaction().execute(
                query,
                {"$group_token": group_token, "$user_id": user.id},
                commit_tx=True,
                settings=ydb.BaseRequestSettings().with_timeout(3).with_operation_timeout(2)
            )

        self.pool.retry_operation_sync(insert_member)

    def leave_group(self, user: UserORM, group_id: int) -> None:
        def delete_member(session):
            query = ydb.DataQuery(
                """
                    DECLARE $group_id AS Int64;
                    DECLARE $user_id AS Int64;
                    DELETE FROM `group_members`
                    WHERE
                        `group_id` == $group_id AND
                        `user_id` == $user_id
                """,
                {"$group_id": ydb.PrimitiveType.Int64, "$user_id": ydb.PrimitiveType.Int64}
            )
            return session.transaction().execute(
                query,
                {"$group_id": group_id, "$user_id": user.id},
                commit_tx=True,
                settings=ydb.BaseRequestSettings().with_timeout(3).with_operation_timeout(2)
            )

        self.pool.retry_operation_sync(delete_member)

    def get_group_expense_list(self, user: UserORM, group_id: int) -> List[ExpenseORM]:
        def select(session):
            query = ydb.DataQuery(
                """
                    DECLARE $group_id AS Int64;
                    DECLARE $user_id AS Int64;
                    $input =
                    SELECT
                        `id`,
                        `name`,
                        `created_at`,
                        `amount`,
                        `currency`,
                        `paid_by`,
                    FROM `expenses`
                    WHERE `group_id` == $group_id
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
                        SOME(`a`.`amount`) * IF (SOME(`a`.`paid_by`) == $user_id, 1, 0) -
                        (SUM_IF(`d`.`amount`, `d`.`user_id` == $user_id) ?? 0) AS `debt_amount`,
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
                """,
                {"$group_id": ydb.PrimitiveType.Int64, "$user_id": ydb.PrimitiveType.Int64}
            )
            return session.transaction().execute(
                query,
                {"$group_id": group_id, "$user_id": user.id},
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
            query = ydb.DataQuery(
                """
                    DECLARE $expense_id AS Int64;
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
                    WHERE `e`.`id` == $expense_id;
                """,
                {"$expense_id": ydb.PrimitiveType.Int64}
            )
            return session.transaction().execute(
                query,
                {"$expense_id": expense_id},
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

    def create_payment(self, group_id: int, expense: ExpenseDraft, name: str) -> None:
        def insert(session):
            tx = session.transaction().begin()

            query1 = ydb.DataQuery(
                """
                    DECLARE $created_at AS Utf8;
                    DECLARE $group_id AS Int64;
                    DECLARE $name AS Utf8;
                    DECLARE $paid_by AS Int64;
                    DECLARE $amount AS Int64;
                    DECLARE $currency AS Int64;
                    INSERT INTO `expenses` (`created_at`, `group_id`, `name`, `paid_by`, `amount`, `currency`)
                    VALUES ($created_at, $group_id, $name, $paid_by, $amount, $currency)
                    RETURNING *
                """,
                {"$created_at": ydb.PrimitiveType.Utf8, "$group_id": ydb.PrimitiveType.Int64, "$name": ydb.PrimitiveType.Utf8, "$paid_by": ydb.PrimitiveType.Int64, "$amount": ydb.PrimitiveType.Int64, "$currency": ydb.PrimitiveType.Int64}
            )
            results = tx.execute(
                query1,
                {
                    "$created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "$group_id": group_id,
                    "$name": name,
                    "$paid_by": expense.user_id,
                    "$amount": expense.amount,
                    "$currency": expense.currency_id,
                },
                commit_tx=False,
                settings=ydb.BaseRequestSettings().with_timeout(3).with_operation_timeout(2)
            )
            expense_id = results[0].rows[0].id

            query2 = ydb.DataQuery(
                """
                    DECLARE $expense_id AS UInt64;
                    DECLARE $user_id AS UInt64;
                    DECLARE $amount AS Int64;
                    INSERT INTO `debts` (`expense_id`, `user_id`, `amount`)
                    VALUES ($expense_id, $user_id, $amount)
                """,
                {"$expense_id": ydb.PrimitiveType.Uint64, "$user_id": ydb.PrimitiveType.Uint64, "$amount": ydb.PrimitiveType.Int64}
            )
            for debt in expense.debts:
                tx.execute(
                    query2,
                    {
                        "$expense_id": expense_id,
                        "$user_id": debt.user_id,
                        "$amount": debt.amount,
                    },
                    commit_tx=False,
                    settings=ydb.BaseRequestSettings().with_timeout(3).with_operation_timeout(2)
                )

            tx.commit()

        self.pool.retry_operation_sync(insert)

    def delete_expense(self, expense_id: int) -> None:
        def delete(session):
            query = ydb.DataQuery(
                """
                    DECLARE $expense_id AS UInt64;
                    DELETE FROM `expenses`
                    WHERE `id` == $expense_id
                    ;
                    DELETE FROM `debts`
                    WHERE `expense_id` == $expense_id
                    ;
                """,
                {"$expense_id": ydb.PrimitiveType.Uint64}
            )
            return session.transaction().execute(
                query,
                {"$expense_id": expense_id},
                commit_tx=True,
                settings=ydb.BaseRequestSettings().with_timeout(3).with_operation_timeout(2)
            )

        self.pool.retry_operation_sync(delete)

    def get_group_balance_list(self, user: UserORM, group_id: int) -> List[BalanceORM]:
        def select(session):
            query = ydb.DataQuery(
                """
                    DECLARE $group_id AS Int64;
                    DECLARE $user_id AS Int64;
                    $input =
                    SELECT
                        `id`,
                        `currency`,
                        `paid_by`,
                    FROM `expenses`
                    WHERE `group_id` == $group_id
                    ;

                    $from_ =
                    SELECT
                        *
                    FROM $input
                    WHERE `paid_by` == $user_id
                    ;

                    $from =
                    SELECT
                        `e`.`currency` AS `currency`,
                        `d`.`user_id` AS `user_id`,
                        `d`.`amount` AS `amount`,
                    FROM $from_ AS `e`
                    LEFT JOIN `debts` AS `d`
                    ON `e`.`id` == `d`.`expense_id`
                    WHERE `user_id` != $user_id
                    ;

                    $to_ =
                    SELECT
                        *
                    FROM $input
                    WHERE `paid_by` != $user_id
                    ;

                    $to =
                    SELECT
                        `e`.`currency` AS `currency`,
                        `e`.`paid_by` AS `user_id`,
                        -`d`.`amount` AS `amount`,
                    FROM $to_ AS `e`
                    INNER JOIN `debts` AS `d`
                    ON `e`.`id` == `d`.`expense_id`
                    WHERE `user_id` == $user_id
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
                """,
                {"$group_id": ydb.PrimitiveType.Int64, "$user_id": ydb.PrimitiveType.Int64}
            )
            return session.transaction().execute(
                query,
                {"$group_id": group_id, "$user_id": user.id},
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

    def paid_premium(self, user: UserORM, expired_date: str) -> None:
        def upsert(session):
            query = ydb.DataQuery(
                """
                    DECLARE $user_id AS Int64;
                    DECLARE $telegram_id AS Utf8;
                    DECLARE $first_name AS Utf8;
                    DECLARE $last_name AS Utf8;
                    DECLARE $expired_date AS Utf8;
                    UPSERT INTO `users` (`id`, `telegram_id`, `first_name`, `last_name`, `expired_date`)
                    VALUES ($user_id, $telegram_id, $first_name, $last_name, $expired_date)
                """,
                {"$user_id": ydb.PrimitiveType.Int64, "$telegram_id": ydb.PrimitiveType.Utf8, "$first_name": ydb.PrimitiveType.Utf8, "$last_name": ydb.PrimitiveType.Utf8, "$expired_date": ydb.PrimitiveType.Utf8}
            )
            return session.transaction().execute(
                query,
                {
                    "$user_id": user.id,
                    "$telegram_id": user.telegram_id,
                    "$first_name": user.first_name,
                    "$last_name": user.last_name,
                    "$expired_date": expired_date,
                },
                commit_tx=True,
                settings=ydb.BaseRequestSettings().with_timeout(3).with_operation_timeout(2)
            )

        self.pool.retry_operation_sync(upsert)

    def batch_insert_exchange_rates(self, rates: list[tuple[int, float]]) -> None:
        created_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        values_str = ', '.join(
            f"('{created_at}', {currency_id}, {rate})"
            for currency_id, rate in rates
        )

        def insert(session):
            session.transaction().execute(
                ydb.DataQuery(
                    f"""
                        INSERT INTO `exchange_rates` (`created_at`, `currency_id`, `rate`)
                        VALUES {values_str}
                    """,
                    {}
                ),
                commit_tx=True,
                settings=ydb.BaseRequestSettings().with_timeout(3).with_operation_timeout(2)
            )

        self.pool.retry_operation_sync(insert)

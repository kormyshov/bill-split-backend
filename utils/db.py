from typing import List

from abstract_base import AbstractBase
from debt_draft import DebtDraft


def create_equally_expense(
        db: AbstractBase,
        user_id_from: int,
        group_id: int,
        expense_name: str,
        amount: int,
        currency_id: int,
        user_ids: List[int]) -> None:

    expense_id = db.create_expense(
        user_id_from,
        group_id,
        expense_name,
        amount,
        currency_id,
    )

    cnt = len(user_ids)

    for i, user_id in enumerate(user_ids):
        db.create_debt(
            expense_id,
            user_id,
            int(
                amount // cnt if i != 0 else
                amount - (amount // cnt) * (cnt - 1)
            )
        )

def create_custom_expense(
        db: AbstractBase,
        user_id_from: int,
        group_id: int,
        expense_name: str,
        amount: int,
        currency_id: int,
        totals: List[DebtDraft],
) -> None:

    expense_id = db.create_expense(
        user_id_from,
        group_id,
        expense_name,
        amount,
        currency_id,
    )

    cnt = len(totals)
    rest = amount

    for i, item in enumerate(totals):
        db.create_debt(
            expense_id,
            item.user_id,
            int(
                item.amount if i != cnt - 1 else rest
            )
        )
        rest -= item.amount

def create_direct_expense(
        db: AbstractBase,
        user_id_from: int,
        user_id_to: int,
        group_id: int,
        name_from: str,
        name_to: str,
        amount: int,
        currency_id: int) -> None:

    expense_id = db.create_expense(
        user_id_from,
        group_id,
        name_from + ' paid ' + name_to,
        amount,
        currency_id,
    )

    db.create_debt(
        expense_id,
        user_id_to,
        amount,
    )

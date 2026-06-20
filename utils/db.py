from typing import List

from debt_draft import DebtDraft
from expense_draft import ExpenseDraft


def create_equally_expense(user_id_from: int, amount: int, currency_id: int, user_ids: List[int]) -> ExpenseDraft:

    debts: List[DebtDraft] = []
    cnt = len(user_ids)

    for i, user_id in enumerate(user_ids):
        debts.append(
            DebtDraft(
                user_id,
                int(
                    amount // cnt if i != 0 else
                    amount - (amount // cnt) * (cnt - 1)
                ),
            )
        )

    return ExpenseDraft(user_id_from, amount, currency_id, debts)


def create_custom_expense(user_id_from: int, amount: int, currency_id: int, totals: List[DebtDraft]) -> ExpenseDraft:

    debts: List[DebtDraft] = []
    cnt = len(totals)
    rest = amount

    for i, item in enumerate(totals):
        debts.append(DebtDraft(
            item.user_id,
            int(
                item.amount if i != cnt - 1 else rest
            ),
        ))
        rest -= item.amount

    return ExpenseDraft(user_id_from, amount, currency_id, debts)

def create_direct_expense(user_id_from: int, user_id_to: int, amount: int, currency_id: int) -> ExpenseDraft:

    debts: List[DebtDraft] = [DebtDraft(user_id_to, amount)]
    return ExpenseDraft(user_id_from, amount, currency_id, debts)

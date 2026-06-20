from typing import List
from typing import NamedTuple
from debt_draft import DebtDraft


class ExpenseDraft(NamedTuple):
    user_id: int
    amount: int
    currency_id: int
    debts: List[DebtDraft]

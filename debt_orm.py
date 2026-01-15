from typing import NamedTuple


class DebtORM(NamedTuple):
    id: int
    expense_name: str
    created_at: str
    total_amount: int
    currency_symbol: str
    paid_by_first_and_last_name: str
    debt_amount: int
    first_and_last_name: str

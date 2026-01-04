from typing import NamedTuple


class ExpenseORM(NamedTuple):
    id: int
    name: str
    created_at: str
    first_and_last_name: str
    amount: int
    currency_symbol: str

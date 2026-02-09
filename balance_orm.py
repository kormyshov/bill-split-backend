from typing import NamedTuple


class BalanceORM(NamedTuple):
    user_id: int
    currency: int
    amount: int
    currency_symbol: str
    first_and_last_name: str

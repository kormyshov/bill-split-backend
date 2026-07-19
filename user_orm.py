from typing import NamedTuple


class UserORM(NamedTuple):
    id: int
    telegram_id: str
    first_name: str
    last_name: str
    expired_date: str
    phone: str

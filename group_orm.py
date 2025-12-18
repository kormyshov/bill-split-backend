import datetime
from typing import NamedTuple


class GroupORM(NamedTuple):
    id: int
    name: str
    created_at: datetime.date

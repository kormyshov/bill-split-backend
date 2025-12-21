from typing import NamedTuple


class GroupORM(NamedTuple):
    id: int
    name: str
    created_at: str
    created_by: int
    count: int

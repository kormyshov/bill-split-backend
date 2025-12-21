from abc import ABC, abstractmethod
from typing import List

from user_orm import UserORM
from group_orm import GroupORM


class AbstractBase(ABC):

    @abstractmethod
    def get_user_info(self, telegram_id: str) -> UserORM:
        pass

    @abstractmethod
    def create_user(self, telegram_id: str, first_name: str, last_name: str) -> None:
        pass

    @abstractmethod
    def get_group_list(self, user: UserORM) -> List[GroupORM]:
        pass

    @abstractmethod
    def create_group(self, user: UserORM, name: str) -> None:
        pass

    @abstractmethod
    def change_group_name(self, group_id: int, name: str, created_at: str, created_by: int) -> None:
        pass


class UserDoesntExistInDB(Exception):
    pass

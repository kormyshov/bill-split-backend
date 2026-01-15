from abc import ABC, abstractmethod
from typing import List

from user_orm import UserORM
from group_orm import GroupORM
from expense_orm import ExpenseORM
from debt_orm import DebtORM


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

    @abstractmethod
    def get_group_member_list(self, group_id: int) -> List[UserORM]:
        pass

    @abstractmethod
    def join_to_group(self, user: UserORM, group_token: str) -> None:
        pass

    @abstractmethod
    def leave_group(self, user: UserORM, group_id: int) -> None:
        pass

    @abstractmethod
    def get_group_expense_list(self, group_id: int) -> List[ExpenseORM]:
        pass

    @abstractmethod
    def get_expense_debt_list(self, expense_id: int) -> List[DebtORM]:
        pass


class UserDoesntExistInDB(Exception):
    pass

from abc import ABC, abstractmethod
from typing import List

from expense_draft import ExpenseDraft
from user_orm import UserORM
from group_orm import GroupORM
from expense_orm import ExpenseORM
from debt_orm import DebtORM
from balance_orm import BalanceORM


class AbstractBase(ABC):

    @abstractmethod
    def get_user_info(self, telegram_id: str) -> UserORM:
        pass

    @abstractmethod
    def create_user(self, telegram_id: str, first_name: str, last_name: str) -> UserORM:
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
    def get_group_expense_list(self, user: UserORM, group_id: int) -> List[ExpenseORM]:
        pass

    @abstractmethod
    def get_expense_debt_list(self, expense_id: int) -> List[DebtORM]:
        pass

    @abstractmethod
    def create_payment(self, group_id: int, expense: ExpenseDraft, name: str) -> None:
        pass

    @abstractmethod
    def delete_expense(self, expense_id: int) -> None:
        pass

    @abstractmethod
    def get_group_balance_list(self, user: UserORM, group_id: int) -> List[BalanceORM]:
        pass

    @abstractmethod
    def paid_premium(self, user: UserORM, expired_date: str) -> None:
        pass

    @abstractmethod
    def update_phone(self, user: UserORM, phone: str) -> None:
        pass

    @abstractmethod
    def delete_phone(self, user: UserORM) -> None:
        pass

    @abstractmethod
    def batch_insert_exchange_rates(self, rates: list[tuple[int, float]]) -> None:
        pass

    @abstractmethod
    def get_latest_exchange_rates(self, currency_id: int) -> list[tuple[int, float]]:
        pass


class UserDoesntExistInDB(Exception):
    pass

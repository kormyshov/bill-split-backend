import pytest

from balance_orm import BalanceORM
from debt_draft import DebtDraft
from expense_draft import ExpenseDraft
from utils.optimize_payments import optimize_payments


def test_empty():
    assert optimize_payments([], 1) == []

def test_one_payment_from():
    assert optimize_payments(
        [
            BalanceORM(2, 1, 123, 'USD', 'Name'),
        ],
        1
    ) == []

def test_one_payment_to():
    assert optimize_payments(
        [
            BalanceORM(2, 1, -123, 'USD', 'Name'),
        ],
        1
    ) == []

def test_one_circle():
    assert optimize_payments(
        [
            BalanceORM(2, 1, 123, 'USD', 'Name One'),
            BalanceORM(3, 1, -321, 'USD', 'Name Two'),
        ],
        1
    ) == [
        ExpenseDraft(1, 123, 1, [DebtDraft(3, 123)]),
        ExpenseDraft(2, 123, 1, [DebtDraft(1, 123)]),
        ExpenseDraft(3, 123, 1, [DebtDraft(2, 123)]),
    ]

def test_different_currencies():
    assert optimize_payments(
        [
            BalanceORM(2, 1, 123, 'USD', 'Name One'),
            BalanceORM(3, 2, -321, 'EUR', 'Name Two'),
        ],
        1
    ) == []

def test_two_circles():
    assert optimize_payments(
        [
            BalanceORM(2, 1, 123, 'USD', 'Name One'),
            BalanceORM(3, 1, -321, 'USD', 'Name Two'),
            BalanceORM(4, 1, 65, 'USD', 'Name Three'),
        ],
        1
    ) == [
        ExpenseDraft(1, 188, 1, [DebtDraft(3, 188)]),
        ExpenseDraft(2, 123, 1, [DebtDraft(1, 123)]),
        ExpenseDraft(3, 188, 1, [DebtDraft(2, 123), DebtDraft(4, 65)]),
        ExpenseDraft(4, 65, 1, [DebtDraft(1, 65)]),
    ]

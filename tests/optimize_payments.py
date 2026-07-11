import random

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


def check_expense_consistency(expenses):
    for exp in expenses:
        assert exp.amount > 0
        assert exp.amount == sum(d.amount for d in exp.debts)
        for d in exp.debts:
            assert d.amount > 0


def test_random_large():
    random.seed(42)

    currencies = ['USD', 'EUR', 'RUB']
    user_ids = list(range(10, 50))
    num_balances = 1000

    for _ in range(20):
        balances = []
        for _ in range(num_balances):
            uid = random.choice(user_ids)
            curr = random.randint(1, len(currencies))
            amount = random.randint(-500, 500)
            if amount == 0:
                amount = 1
            sym = currencies[curr - 1]
            name = f'U{uid}'
            balances.append(BalanceORM(uid, curr, amount, sym, name))

        result = optimize_payments(balances, 1)
        check_expense_consistency(result)


def test_random_balanced():
    random.seed(123)

    for _ in range(20):
        balances = []
        for uid in range(10, 30):
            curr = random.randint(1, 3)
            amount = random.randint(1, 100)
            if random.random() < 0.5:
                amount = -amount
            sym = ['USD', 'EUR', 'RUB'][curr - 1]
            balances.append(BalanceORM(uid, curr, amount, sym, f'U{uid}'))

        result = optimize_payments(balances, 5)
        check_expense_consistency(result)

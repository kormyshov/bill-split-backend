import pytest

from debt_draft import DebtDraft
from expense_draft import ExpenseDraft
from utils.db import (
    create_direct_expense,
    create_equally_expense,
    create_custom_expense,
)


def test_direct():
    assert create_direct_expense(3, 4, 123, 2) == ExpenseDraft(3, 123, 2, [DebtDraft(4, 123)])


def test_equally():
    assert create_equally_expense(
        3, 123, 2, [5, 6, 7]
    ) == ExpenseDraft(
        3, 123, 2, [
            DebtDraft(5, 41),
            DebtDraft(6, 41),
            DebtDraft(7, 41),
        ],
    )


def test_almost_equally():
    assert create_equally_expense(
        3, 122, 2, [5, 6, 7]
    ) == ExpenseDraft(3, 122, 2, [
        DebtDraft(5, 42),
        DebtDraft(6, 40),
        DebtDraft(7, 40),
    ])


def test_custom():
    assert create_custom_expense(
        3, 123, 2, [
            DebtDraft(5, 42),
            DebtDraft(6, 40),
        ]
    ) == ExpenseDraft(3, 123, 2, [
        DebtDraft(5, 42),
        DebtDraft(6, 81),
    ])

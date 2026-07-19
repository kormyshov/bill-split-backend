import logging

from abstract_base import AbstractBase
from user_orm import UserORM
from debt_draft import DebtDraft
from utils.db import (
    create_equally_expense,
    create_custom_expense,
    create_direct_expense,
)
from utils.optimize_payments import optimize_payments
from . import decode_body, parse_json_body, json_response

logger = logging.getLogger(__name__)


def get_debt_list(db: AbstractBase, user: UserORM, event: dict) -> dict:
    expense_id = int(event['queryStringParameters']['expense_id'])
    expense_debts = db.get_expense_debt_list(expense_id)
    logger.debug('Debt list fetched', extra={'extra_data': {'expense_id': expense_id, 'count': len(expense_debts)}})
    return json_response({"expense_debts": expense_debts})


def create_equally(db: AbstractBase, user: UserORM, event: dict) -> None:
    input = parse_json_body(event)
    draft = create_equally_expense(
        input['payer_id'],
        int(input['expense_amount'] * 100),
        input['expense_currency'],
        input['user_ids'],
    )
    db.create_payment(int(input['group_id']), draft, input['expense_name'])
    logger.info('Equal expense created', extra={'extra_data': {
        'group_id': input['group_id'],
        'name': input['expense_name'],
        'amount': input['expense_amount'],
    }})


def create_custom(db: AbstractBase, user: UserORM, event: dict) -> None:
    input = parse_json_body(event)
    draft = create_custom_expense(
        input['payer_id'],
        int(input['expense_amount'] * 100),
        input['expense_currency'],
        [DebtDraft(x['memberId'], int(x['total'] * 100)) for x in input['totals']],
    )
    db.create_payment(int(input['group_id']), draft, input['expense_name'])
    logger.info('Custom expense created', extra={'extra_data': {
        'group_id': input['group_id'],
        'name': input['expense_name'],
        'amount': input['expense_amount'],
    }})


def create_direct(db: AbstractBase, user: UserORM, event: dict) -> None:
    input = parse_json_body(event)
    if int(input['amount']) < 0:
        draft = create_direct_expense(
            user.id,
            input['user_id'],
            -int(input['amount']),
            input['currency'],
        )
        name = user.first_name + ' ' + user.last_name + ' paid ' + input['first_and_last_name']
    else:
        draft = create_direct_expense(
            input['user_id'],
            user.id,
            int(input['amount']),
            input['currency'],
        )
        name = input['first_and_last_name'] + ' paid ' + user.first_name + ' ' + user.last_name
    db.create_payment(int(input['group_id']), draft, name)
    logger.info('Direct expense created', extra={'extra_data': {
        'group_id': input['group_id'],
        'amount': input['amount'],
    }})


def delete_expense(db: AbstractBase, user: UserORM, event: dict) -> None:
    expense_id = int(decode_body(event))
    db.delete_expense(expense_id)
    logger.info('Expense deleted', extra={'extra_data': {'expense_id': expense_id, 'user_id': user.id}})


def optimize(db: AbstractBase, user: UserORM, event: dict) -> None:
    input = parse_json_body(event)
    group_id = int(input['group_id'])
    group_balances = db.get_group_balance_list(user, group_id)
    draft = optimize_payments(group_balances, user.id)
    for item in draft:
        db.create_payment(group_id, item, 'Optimize for ' + user.first_name + ' ' + user.last_name)
    logger.info('Payments optimized', extra={'extra_data': {
        'group_id': group_id,
        'transactions': len(draft),
    }})

from abstract_base import AbstractBase
from user_orm import UserORM
from . import decode_body, parse_json_body, json_response


def get_group_list(db: AbstractBase, user: UserORM, event: dict) -> dict:
    groups = db.get_group_list(user)
    return json_response({"groups": groups})


def create_group(db: AbstractBase, user: UserORM, event: dict) -> None:
    group_name = decode_body(event)
    db.create_group(user, group_name)


def change_group_name(db: AbstractBase, user: UserORM, event: dict) -> None:
    input = parse_json_body(event)
    db.change_group_name(input['group_id'], input['name'], input['created_at'], input['created_by'])


def get_member_list(db: AbstractBase, user: UserORM, event: dict) -> dict:
    group_id = int(event['queryStringParameters']['group_id'])
    group_members = db.get_group_member_list(group_id)
    return json_response({"group_members": group_members})


def join_group(db: AbstractBase, user: UserORM, event: dict) -> None:
    group_token = decode_body(event)
    db.join_to_group(user, group_token)


def leave_group(db: AbstractBase, user: UserORM, event: dict) -> None:
    group_id = int(decode_body(event))
    db.leave_group(user, group_id)


def get_expense_list(db: AbstractBase, user: UserORM, event: dict) -> dict:
    group_id = int(event['queryStringParameters']['group_id'])
    group_expenses = db.get_group_expense_list(user, group_id)
    return json_response({"group_expenses": group_expenses})


def get_balance_list(db: AbstractBase, user: UserORM, event: dict) -> dict:
    group_id = int(event['queryStringParameters']['group_id'])
    group_balances = db.get_group_balance_list(user, group_id)
    return json_response({"group_balances": group_balances})

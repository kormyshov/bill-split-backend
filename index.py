import json
from typing import Callable, Optional

from utils.validates import (
    validate_telegram_data,
    validate_init_db,
)
from abstract_base import (
    AbstractBase,
    UserDoesntExistInDB,
)
from database import Database
from user_orm import UserORM

from handlers.account import get_account_info
from handlers.groups import (
    get_group_list,
    create_group,
    change_group_name,
    get_member_list,
    join_group,
    leave_group,
    get_expense_list,
    get_balance_list,
)
from handlers.expenses import (
    get_debt_list,
    create_equally,
    create_custom,
    create_direct,
    delete_expense,
    optimize,
)
from handlers.rates import update_rates, get_rates
from handlers.stars import (
    create_invoice_link,
    paid_premium,
)
from handlers.phone import set_phone, delete_phone

HandlerFunc = Callable[[AbstractBase, UserORM, dict], Optional[dict]]

METHOD_HANDLERS: dict[str, HandlerFunc] = {
    'account/get_info': get_account_info,
    'groups/get_list': get_group_list,
    'groups/create': create_group,
    'groups/change_name': change_group_name,
    'groups/get_member_list': get_member_list,
    'groups/join': join_group,
    'groups/leave': leave_group,
    'groups/get_expense_list': get_expense_list,
    'groups/get_balance_list': get_balance_list,
    'expenses/get_debt_list': get_debt_list,
    'expenses/create_equally': create_equally,
    'expenses/create_custom': create_custom,
    'expenses/create_direct': create_direct,
    'expenses/delete': delete_expense,
    'expenses/optimize': optimize,
    'stars/create_invoice_link': create_invoice_link,
    'stars/paid_premium': paid_premium,
    'rates/get_rates': get_rates,
    'phone/set': set_phone,
    'phone/delete': delete_phone,
}


def handler(event, context):

    print(event)
    print(context)

    if 'httpMethod' not in event:
        db: AbstractBase = Database()
        return update_rates(db)

    if event['httpMethod'] == 'GET' or event['httpMethod'] == 'POST':
        db: AbstractBase = Database()
        try:
            user: UserORM = db.get_user_info(event['queryStringParameters']['user_id'])
        except UserDoesntExistInDB:
            db.create_user(
                event['queryStringParameters']['user_id'],
                event['queryStringParameters']['first_name'],
                event['queryStringParameters']['last_name'],
            )

            user: UserORM = db.get_user_info(event['queryStringParameters']['user_id'])
        except KeyError:
            if 'pre_checkout_query' in event['body']:
                query_id = json.loads(event['body'])['pre_checkout_query']['id']
                return {
                    'statusCode': 200,
                    'headers': {"Content-Type": "application/json"},
                    'body': json.dumps({"ok": True, "pre_checkout_query_id": query_id}),
                }

            return {
                'statusCode': 200,
                'headers': {"Content-Type": "application/json"},
                'body': json.dumps({"ok": True, "error": "KeyError"}),
            }

        method = event['queryStringParameters']['method']

        if method == 'init_db' and validate_init_db(event['queryStringParameters']['user_id']):
            return {
                'statusCode': 200,
                'headers': {"Content-Type": "application/json"},
                'body': json.dumps({"ok": True}),
            }

        if event['queryStringParameters']['user_id'] == 'test' or validate_telegram_data(
            event['queryStringParameters'].get('validate', '')
        ):
            handler_func = METHOD_HANDLERS.get(method)
            if handler_func:
                result = handler_func(db, user, event)
                if result is not None:
                    return result

    return {
        'statusCode': 200,
        'body': '{}',
    }

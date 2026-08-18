import json
import logging
from typing import Callable, Optional

from logging_setup import setup_logging
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
from handlers.receipts import scan_receipt

setup_logging()
logger = logging.getLogger(__name__)

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
    'receipts/scan': scan_receipt,
}


def handler(event, context):
    # Request bodies may contain receipt photos. Do not log the raw event.
    logger.debug('Incoming event', extra={'extra_data': {
        'http_method': event.get('httpMethod'),
        'has_body': bool(event.get('body')),
    }})
    logger.debug('Incoming context')

    if 'httpMethod' not in event:
        db: AbstractBase = Database()
        result = update_rates(db)
        logger.info('Scheduled rates update completed', extra={'extra_data': {'updated': result}})
        return result

    if event['httpMethod'] == 'GET' or event['httpMethod'] == 'POST':
        db: AbstractBase = Database()
        method = event['queryStringParameters'].get('method', 'unknown')
        user_id = event['queryStringParameters'].get('user_id', 'unknown')

        logger.info('Handling request', extra={'extra_data': {
            'method': method,
            'user_id': user_id,
            'http_method': event['httpMethod'],
        }})

        try:
            user: UserORM = db.get_user_info(event['queryStringParameters']['user_id'])
        except UserDoesntExistInDB:
            user = db.create_user(
                event['queryStringParameters']['user_id'],
                event['queryStringParameters']['first_name'],
                event['queryStringParameters']['last_name'],
            )
            logger.info('User ensured', extra={'extra_data': {'user_id': user.id}})
        except KeyError:
            if 'pre_checkout_query' in event['body']:
                query_id = json.loads(event['body'])['pre_checkout_query']['id']
                logger.info('Pre-checkout query', extra={'extra_data': {'query_id': query_id}})
                return {
                    'statusCode': 200,
                    'headers': {"Content-Type": "application/json"},
                    'body': json.dumps({"ok": True, "pre_checkout_query_id": query_id}),
                }

            logger.warning('KeyError in request', extra={'extra_data': {
                'http_method': event.get('httpMethod'),
                'query_keys': sorted((event.get('queryStringParameters') or {}).keys()),
            }})
            return {
                'statusCode': 200,
                'headers': {"Content-Type": "application/json"},
                'body': json.dumps({"ok": True, "error": "KeyError"}),
            }

        method = event['queryStringParameters']['method']

        if method == 'init_db' and validate_init_db(event['queryStringParameters']['user_id']):
            logger.info('init_db request')
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
                logger.info('Executing handler', extra={'extra_data': {'method': method}})
                result = handler_func(db, user, event)
                if result is not None:
                    return result

        logger.warning('No handler executed', extra={'extra_data': {'method': method}})

    return {
        'statusCode': 200,
        'body': '{}',
    }

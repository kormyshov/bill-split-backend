import base64
from datetime import datetime, timedelta
import json
import requests

from config import Config
from debt_draft import DebtDraft
from utils.optimize_payments import optimize_payments
from utils.validates import (
    validate_telegram_data,
    validate_init_db,
)
from utils.db import (
    create_equally_expense,
    create_custom_expense,
    create_direct_expense,
)
from abstract_base import (
    AbstractBase,
    UserDoesntExistInDB,
)
from database import Database
from user_orm import UserORM


def handler(event, context):

    print(event, flush=True)
    print(context, flush=True)

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
                    'body': '''
                        {
                            "ok": True,
                            "pre_checkout_query_id": "''' + query_id + '''"
                        }
                    ''',
                }

            return {
                'statusCode': 200,
                'body': '{"ok": True, "error": "KeyError"}',
            }

        if event['queryStringParameters']['method'] == 'init_db' and validate_init_db(event['queryStringParameters']['user_id']):
            pass

        if event['queryStringParameters']['user_id'] == 'test' or validate_telegram_data(event['queryStringParameters'].get('validate', '')):
            if event['queryStringParameters']['method'] == 'account/get_info':
                return {
                    'statusCode': 200,
                    'body': '''
                        {
                            "account": ''' + json.dumps(user) + '''
                        }
                    ''',
                }

            if event['queryStringParameters']['method'] == 'groups/get_list':
                groups = db.get_group_list(user)

                return {
                    'statusCode': 200,
                    'body': '''
                        {
                            "groups": ''' + json.dumps(groups) + '''                    
                        }
                    ''',
                }

            if event['queryStringParameters']['method'] == 'groups/create':
                group_name = base64.b64decode(event['body']).decode('utf-8')
                db.create_group(user, group_name)

            if event['queryStringParameters']['method'] == 'groups/change_name':
                input = json.loads(base64.b64decode(event['body']).decode('utf-8'))
                db.change_group_name(input['group_id'], input['name'], input['created_at'], input['created_by'])

            if event['queryStringParameters']['method'] == 'groups/get_member_list':
                group_id = int(event['queryStringParameters']['group_id'])
                group_members = db.get_group_member_list(group_id)

                return {
                    'statusCode': 200,
                    'body': '''
                        {
                            "group_members": ''' + json.dumps(group_members) + '''                    
                        }
                    ''',
                }

            if event['queryStringParameters']['method'] == 'groups/join':
                group_token = base64.b64decode(event['body']).decode('utf-8')
                db.join_to_group(user, group_token)

            if event['queryStringParameters']['method'] == 'groups/leave':
                group_id = int(base64.b64decode(event['body']).decode('utf-8'))
                db.leave_group(user, group_id)

            if event['queryStringParameters']['method'] == 'groups/get_expense_list':
                group_id = int(event['queryStringParameters']['group_id'])
                group_expenses = db.get_group_expense_list(user, group_id)

                return {
                    'statusCode': 200,
                    'body': '''
                        {
                            "group_expenses": ''' + json.dumps(group_expenses) + '''                    
                        }
                    ''',
                }

            if event['queryStringParameters']['method'] == 'expenses/get_debt_list':
                expense_id = int(event['queryStringParameters']['expense_id'])
                expense_debts = db.get_expense_debt_list(expense_id)

                return {
                    'statusCode': 200,
                    'body': '''
                        {
                            "expense_debts": ''' + json.dumps(expense_debts) + '''                    
                        }
                    ''',
                }

            if event['queryStringParameters']['method'] == 'expenses/create_equally':
                input = json.loads(base64.b64decode(event['body']).decode('utf-8'))
                draft = create_equally_expense(
                    input['payer_id'],
                    int(input['expense_amount'] * 100),
                    input['expense_currency'],
                    input['user_ids'],
                )
                db.create_payment(input['group_id'], draft, input['expense_name'])

            if event['queryStringParameters']['method'] == 'expenses/create_custom':
                input = json.loads(base64.b64decode(event['body']).decode('utf-8'))
                draft = create_custom_expense(
                    input['payer_id'],
                    int(input['expense_amount'] * 100),
                    input['expense_currency'],
                    [DebtDraft(x['memberId'], int(x['total'] * 100)) for x in input['totals']],
                )
                db.create_payment(input['group_id'], draft, input['expense_name'])

            if event['queryStringParameters']['method'] == 'expenses/create_direct':
                input = json.loads(base64.b64decode(event['body']).decode('utf-8'))
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
                db.create_payment(input['group_id'], draft, name)

            if event['queryStringParameters']['method'] == 'expenses/delete':
                expense_id = int(base64.b64decode(event['body']).decode('utf-8'))
                db.delete_expense(expense_id)

            if event['queryStringParameters']['method'] == 'groups/get_balance_list':
                group_id = int(event['queryStringParameters']['group_id'])
                group_balances = db.get_group_balance_list(user, group_id)

                return {
                    'statusCode': 200,
                    'body': '''
                        {
                            "group_balances": ''' + json.dumps(group_balances) + '''                    
                        }
                    ''',
                }

            if event['queryStringParameters']['method'] == 'expenses/optimize':
                input = json.loads(base64.b64decode(event['body']).decode('utf-8'))
                group_id = input['group_id']
                group_balances = db.get_group_balance_list(user, group_id)
                draft = optimize_payments(group_balances, user.id)
                for item in draft:
                    db.create_payment(group_id, item, 'Optimize for ' + user.first_name + ' ' + user.last_name)

            if event['queryStringParameters']['method'] == 'stars/create_invoice_link':
                input = json.loads(base64.b64decode(event['body']).decode('utf-8'))
                stars = str(input['stars'])
                days = str(input['days'])
                response = requests.get(
                    'https://api.telegram.org/bot' + Config.BOT_TOKEN + '/createInvoiceLink',
                    params={
                        'title': 'Premium for ' + days + ' days',
                        'description': 'Pay ' + stars + ' stars for ' + days + ' days of Premium',
                        'payload': str(user.id) + ' ' + days,
                        'currency': 'XTR',
                        'prices': json.dumps([{'label': 'Stars', 'amount': stars}]),
                    }
                )

                return {
                    'statusCode': 200,
                    'body': '''
                        {
                            "invoice_link": ''' + response.text + '''                    
                        }
                    ''',
                }

            if event['queryStringParameters']['method'] == 'stars/paid_premium':
                input = json.loads(base64.b64decode(event['body']).decode('utf-8'))
                days = input['days']
                today = datetime.today().strftime('%Y-%m-%d')
                expired_date = datetime.strptime(max(today, user.expired_date), '%Y-%m-%d') + timedelta(days=days)
                db.paid_premium(user, expired_date.strftime('%Y-%m-%d'))

    return {
        'statusCode': 200,
        'body': '{}',
    }

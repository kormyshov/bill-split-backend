import base64
import json
from utils import (
    validate_telegram_data,
    validate_init_db,
)
from abstract_base import (
    AbstractBase,
    UserDoesntExistInDB,
)
from database import Database
from user_orm import UserORM


def handler(event, context):

    print(event)
    print(context)

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
                expense_id = db.create_expense(
                    input['payer_id'],
                    input['group_id'],
                    input['expense_name'],
                    int(input['expense_amount'] * 100),
                    input['expense_currency'],
                )

                cnt = len(input['user_ids'])

                for i, user_id in enumerate(input['user_ids']):
                    db.create_debt(
                        expense_id,
                        user_id,
                        int(
                            input['expense_amount'] * 100 // cnt if i != 0 else
                            input['expense_amount'] * 100 - (input['expense_amount'] * 100 // cnt) * (cnt - 1)
                        )
                    )

            if event['queryStringParameters']['method'] == 'expenses/create_custom':
                input = json.loads(base64.b64decode(event['body']).decode('utf-8'))
                expense_id = db.create_expense(
                    input['payer_id'],
                    input['group_id'],
                    input['expense_name'],
                    int(input['expense_amount'] * 100),
                    input['expense_currency'],
                )

                cnt = len(input['totals'])
                rest = int(input['expense_amount'] * 100)

                for i, item in enumerate(input['totals']):
                    db.create_debt(
                        expense_id,
                        item['memberId'],
                        int(
                            int(item['total'] * 100) if i != cnt - 1 else rest
                        )
                    )
                    rest -= int(item['total'] * 100)

            if event['queryStringParameters']['method'] == 'expenses/create_direct':
                input = json.loads(base64.b64decode(event['body']).decode('utf-8'))
                if int(input['amount']) < 0:
                    expense_id = db.create_expense(
                        user.id,
                        input['group_id'],
                        user.first_name + ' ' + user.last_name + ' paid ' + input['first_and_last_name'],
                        -int(input['amount']),
                        input['currency'],
                    )

                    db.create_debt(
                        expense_id,
                        input['user_id'],
                        -int(input['amount']),
                    )
                else:
                    expense_id = db.create_expense(
                        input['user_id'],
                        input['group_id'],
                        input['first_and_last_name'] + ' paid ' + user.first_name + ' ' + user.last_name,
                        int(input['amount']),
                        input['currency'],
                        )

                    db.create_debt(
                        expense_id,
                        user.id,
                        int(input['amount']),
                    )

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

    return {
        'statusCode': 200,
        'body': '{}',
    }

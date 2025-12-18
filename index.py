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

            return {
                'statusCode': 200,
                'body': '{"groups": []}',
            }

        if event['queryStringParameters']['method'] == 'init_db' and validate_init_db(event['queryStringParameters']['user_id']):
            pass

        if event['queryStringParameters']['user_id'] == 'test' or validate_telegram_data(event['queryStringParameters'].get('validate', '')):
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

    return {
        'statusCode': 200,
        'body': '{}',
    }

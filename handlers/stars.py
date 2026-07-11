import json
from datetime import datetime, timedelta

import requests

from abstract_base import AbstractBase
from config import Config
from user_orm import UserORM
from . import parse_json_body, json_response


def create_invoice_link(db: AbstractBase, user: UserORM, event: dict) -> dict:
    input = parse_json_body(event)
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
        },
    )

    return json_response({"invoice_link": response.text})


def paid_premium(db: AbstractBase, user: UserORM, event: dict) -> None:
    input = parse_json_body(event)
    days = input['days']
    today = datetime.today().strftime('%Y-%m-%d')
    expired_date = datetime.strptime(max(today, user.expired_date), '%Y-%m-%d') + timedelta(days=days)
    db.paid_premium(user, expired_date.strftime('%Y-%m-%d'))

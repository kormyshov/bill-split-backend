import requests

from abstract_base import AbstractBase
from constants.currencies import CODE_TO_ID
from user_orm import UserORM
from . import json_response, parse_json_body


def update_rates(db: AbstractBase) -> dict:
    response = requests.get('https://www.floatrates.com/daily/USD.json', timeout=10)
    data = response.json()

    batch = []
    for code, info in data.items():
        currency_id = CODE_TO_ID.get(info['code'])
        if currency_id is not None:
            batch.append((currency_id, float(info['rate'])))

    if batch:
        db.batch_insert_exchange_rates(batch)

    return json_response({"ok": True, "updated": len(batch)})


def get_rates(db: AbstractBase, user: UserORM, event: dict) -> dict:
    body = parse_json_body(event)
    currency_id = int(body['currency_id'])
    rates = db.get_latest_exchange_rates(currency_id)
    return json_response({"rates": dict(rates)})

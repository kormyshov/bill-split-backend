import requests

from abstract_base import AbstractBase
from . import json_response


def update_rates(db: AbstractBase) -> dict:
    response = requests.get('https://www.floatrates.com/daily/USD.json', timeout=10)
    data = response.json()

    for code, info in data.items():
        currency_id = db.upsert_currency(info['code'], info['name'])
        db.insert_exchange_rate(currency_id, float(info['rate']))

    return json_response({"ok": True, "updated": len(data)})

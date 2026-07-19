import logging

import requests

from abstract_base import AbstractBase
from constants.currencies import CODE_TO_ID
from user_orm import UserORM
from . import json_response, parse_json_body

logger = logging.getLogger(__name__)


def update_rates(db: AbstractBase) -> dict:
    logger.info('Fetching exchange rates from floatrates.com')
    try:
        response = requests.get('https://www.floatrates.com/daily/USD.json', timeout=10)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        logger.error('Failed to fetch exchange rates', extra={'extra_data': {'error': str(e)}})
        raise

    batch = [(1, 1.0)]
    for code, info in data.items():
        currency_id = CODE_TO_ID.get(info['code'])
        if currency_id is not None and currency_id != 1:
            batch.append((currency_id, float(info['rate'])))

    if batch:
        db.batch_insert_exchange_rates(batch)

    logger.info('Exchange rates updated', extra={'extra_data': {'count': len(batch)}})
    return json_response({"ok": True, "updated": len(batch)})


def get_rates(db: AbstractBase, user: UserORM, event: dict) -> dict:
    body = parse_json_body(event)
    currency_id = int(body['currency_id'])
    rates = db.get_latest_exchange_rates(currency_id)
    logger.debug('Rates fetched', extra={'extra_data': {'currency_id': currency_id, 'count': len(rates)}})
    return json_response({"rates": dict(rates)})

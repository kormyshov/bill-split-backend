import logging
import re

from abstract_base import AbstractBase
from user_orm import UserORM
from . import parse_json_body, json_response

logger = logging.getLogger(__name__)

PHONE_PATTERN = re.compile(r'^\+[1-9]\d{6,14}$')


def set_phone(db: AbstractBase, user: UserORM, event: dict) -> dict:
    input = parse_json_body(event)
    phone = input.get('phone', '').strip()

    if not PHONE_PATTERN.match(phone):
        logger.warning('Invalid phone format', extra={'extra_data': {'user_id': user.id}})
        return json_response({"ok": False, "error": "Invalid phone format"})

    db.update_phone(user, phone)
    logger.info('Phone updated', extra={'extra_data': {'user_id': user.id}})
    return json_response({"ok": True})


def delete_phone(db: AbstractBase, user: UserORM, event: dict) -> dict:
    db.delete_phone(user)
    logger.info('Phone deleted', extra={'extra_data': {'user_id': user.id}})
    return json_response({"ok": True})

import re

from abstract_base import AbstractBase
from user_orm import UserORM
from . import parse_json_body, json_response

PHONE_PATTERN = re.compile(r'^\+[1-9]\d{6,14}$')


def set_phone(db: AbstractBase, user: UserORM, event: dict) -> dict:
    input = parse_json_body(event)
    phone = input.get('phone', '').strip()

    if not PHONE_PATTERN.match(phone):
        return json_response({"ok": False, "error": "Invalid phone format"})

    db.update_phone(user, phone)
    return json_response({"ok": True})


def delete_phone(db: AbstractBase, user: UserORM, event: dict) -> dict:
    db.delete_phone(user)
    return json_response({"ok": True})

from abstract_base import AbstractBase
from user_orm import UserORM
from . import json_response


def get_account_info(db: AbstractBase, user: UserORM, event: dict) -> dict:
    return json_response({"account": user})

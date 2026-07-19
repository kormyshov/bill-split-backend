import logging

from abstract_base import AbstractBase
from user_orm import UserORM
from . import json_response

logger = logging.getLogger(__name__)


def get_account_info(db: AbstractBase, user: UserORM, event: dict) -> dict:
    logger.debug('Account info fetched', extra={'extra_data': {'user_id': user.id}})
    return json_response({"account": user})

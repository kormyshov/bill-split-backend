import hmac
import hashlib
import logging
from urllib.parse import unquote
from config import Config

logger = logging.getLogger(__name__)


def validate_telegram_data(data: str) -> bool:
    sorted_params = []
    hash = ''
    auth_date = -1
    for param in sorted(unquote(data).split('&')):
        if param.startswith('hash='):
            hash = param[5:]
            continue
        if param.startswith('auth_date='):
            auth_date = int(param[10:])
        sorted_params.append(param)
    if hash == '' or auth_date == -1:
        logger.warning('Telegram validation failed: missing hash or auth_date')
        return False
    valid = hmac.new(Config.SECRET_KEY, '\n'.join(sorted_params).encode(), hashlib.sha256).hexdigest() == hash
    if not valid:
        logger.warning('Telegram validation failed: HMAC mismatch')
    return valid


def validate_init_db(user: str) -> bool:
    result = Config.BOT_TOKEN == user
    if not result:
        logger.warning('init_db validation failed')
    return result

import hmac
import hashlib
from urllib.parse import unquote
from config import Config


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
        return False
    return hmac.new(Config.SECRET_KEY, '\n'.join(sorted_params).encode(), hashlib.sha256).hexdigest() == hash


def validate_init_db(user: str) -> bool:
    return Config.BOT_TOKEN == user

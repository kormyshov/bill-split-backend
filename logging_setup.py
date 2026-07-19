import json
import logging
import datetime
import os


LOG_LEVEL_ENV = 'LOG_LEVEL'


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            'timestamp': datetime.datetime.fromtimestamp(
                record.created, tz=datetime.timezone.utc
            ).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
        }
        if record.exc_info and record.exc_info[0]:
            log_entry['exception'] = self.formatException(record.exc_info)
        extra = getattr(record, 'extra_data', None)
        if extra:
            log_entry.update(extra)
        return json.dumps(log_entry, ensure_ascii=False)


def setup_logging() -> None:
    level = os.environ.get(LOG_LEVEL_ENV, 'INFO').upper()

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(handler)

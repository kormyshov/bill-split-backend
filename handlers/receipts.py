import base64
import binascii
from datetime import date, datetime
import json
import logging
from typing import Any

import requests

from abstract_base import AbstractBase
from config import Config
from user_orm import UserORM
from . import json_response, parse_json_body


logger = logging.getLogger(__name__)

OCR_URL = 'https://ai.api.cloud.yandex.net/ocr/v1/recognizeText'
COMPLETIONS_URL = 'https://ai.api.cloud.yandex.net/v1/chat/completions'
PARSER_MODEL = 'yandexgpt-5-lite'
MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024
SUPPORTED_MIME_TYPES = {'image/jpeg': 'JPEG', 'image/png': 'PNG'}
RECEIPT_SCHEMA = {
    'name': 'receipt',
    'schema': {
        'type': 'object',
        'properties': {
            'total': {
                'type': 'number',
                'description': 'The final amount paid. Omit when it cannot be determined.',
            },
            'currency': {
                'type': 'string',
                'description': 'ISO 4217 currency code. Omit when it cannot be determined.',
            },
            'items': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': {
                        'name': {'type': 'string'},
                        'price': {
                            'type': 'number',
                            'description': 'Final price for the whole receipt line.',
                        },
                        'quantity': {
                            'type': 'number',
                            'description': 'Item quantity. Omit when it is not printed.',
                        },
                    },
                    'required': ['name', 'price'],
                },
            },
        },
        'required': ['items'],
    },
}


def _text_from_line(line: dict[str, Any]) -> str:
    if isinstance(line.get('text'), str):
        return line['text'].strip()
    words = line.get('words') or []
    return ' '.join(word.get('text', '') for word in words if isinstance(word, dict)).strip()


def _extract_lines(node: Any) -> list[str]:
    """Extract OCR lines from Vision's nested blocks without retaining the response."""
    if isinstance(node, list):
        return [line for item in node for line in _extract_lines(item)]
    if not isinstance(node, dict):
        return []

    if 'words' in node or 'text' in node and 'lines' not in node:
        text = _text_from_line(node)
        return [text] if text else []

    lines: list[str] = []
    for key in ('blocks', 'lines'):
        if key in node:
            lines.extend(_extract_lines(node[key]))
    if lines:
        return lines
    for value in node.values():
        if isinstance(value, (dict, list)):
            lines.extend(_extract_lines(value))
    return lines


def extract_receipt_text(vision_response: dict[str, Any]) -> str:
    """Flatten Vision OCR lines while preserving their order."""
    result = vision_response.get('result', vision_response)
    annotation = result.get('textAnnotation', result) if isinstance(result, dict) else {}
    return '\n'.join(_extract_lines(annotation))


def _normalize_receipt(receipt: Any) -> dict[str, Any]:
    if not isinstance(receipt, dict) or not isinstance(receipt.get('items'), list):
        raise ValueError('The model returned an invalid receipt')

    normalized_items = []
    for item in receipt['items']:
        if not isinstance(item, dict):
            continue
        name = item.get('name')
        price = item.get('price')
        if not isinstance(name, str) or not name.strip() or not isinstance(price, (int, float)):
            continue
        normalized_item: dict[str, Any] = {'name': name.strip(), 'price': float(price)}
        quantity = item.get('quantity')
        if isinstance(quantity, (int, float)) and quantity > 0:
            normalized_item['quantity'] = float(quantity)
        normalized_items.append(normalized_item)

    total = receipt.get('total')
    currency = receipt.get('currency')
    return {
        'total': float(total) if isinstance(total, (int, float)) else None,
        'currency': currency.strip().upper() if isinstance(currency, str) and currency.strip() else None,
        'items': normalized_items,
    }


def parse_receipt(ocr_text: str) -> dict[str, Any]:
    """Extract a receipt draft from OCR text with a structured YandexGPT response."""
    response = requests.post(
        COMPLETIONS_URL,
        headers={
            'Authorization': 'Api-Key ' + Config.YANDEX_API_KEY,
            'Content-Type': 'application/json',
            'OpenAI-Project': Config.YANDEX_FOLDER_ID,
            'x-data-logging-enabled': 'false',
        },
        json={
            'model': 'gpt://' + Config.YANDEX_FOLDER_ID + '/' + PARSER_MODEL,
            'messages': [
                {
                    'role': 'system',
                    'content': (
                        'Extract a receipt from OCR text. Use only evidence present in the text. '
                        'Do not invent items or amounts. Normalize currency to an ISO 4217 code. '
                        'The item price is the final amount for that receipt line, not a unit price.'
                    ),
                },
                {'role': 'user', 'content': ocr_text},
            ],
            'temperature': 0,
            'max_tokens': 2000,
            'stream': False,
            'response_format': {'type': 'json_schema', 'json_schema': RECEIPT_SCHEMA},
        },
        timeout=20,
    )
    response.raise_for_status()
    content = response.json()['choices'][0]['message']['content']
    return _normalize_receipt(json.loads(content))


def _has_premium(user: UserORM) -> bool:
    return datetime.strptime(user.expired_date, '%Y-%m-%d').date() >= date.today()


def _decode_image(encoded_image: str) -> bytes:
    try:
        image = base64.b64decode(encoded_image, validate=True)
    except (binascii.Error, ValueError) as error:
        raise ValueError('image_base64 must contain valid Base64 data') from error
    if not image:
        raise ValueError('image_base64 must not be empty')
    if len(image) > MAX_IMAGE_SIZE_BYTES:
        raise ValueError('Image must not exceed 10 MB')
    return image


def scan_receipt(db: AbstractBase, user: UserORM, event: dict) -> dict:
    """Recognize a receipt without writing its image or OCR response to storage."""
    if not _has_premium(user):
        return json_response({'error': 'Premium subscription is required'}, status_code=403)
    if not Config.YANDEX_API_KEY or not Config.YANDEX_FOLDER_ID:
        logger.error('Vision OCR is not configured')
        return json_response({'error': 'Receipt scanning is temporarily unavailable'}, status_code=503)

    try:
        payload = parse_json_body(event)
        mime_type = payload.get('mime_type', 'image/jpeg').lower()
        image_type = SUPPORTED_MIME_TYPES.get(mime_type)
        if image_type is None:
            raise ValueError('mime_type must be image/jpeg or image/png')
        image = _decode_image(payload['image_base64'])
    except (KeyError, TypeError, ValueError) as error:
        return json_response({'error': str(error)}, status_code=400)

    try:
        response = requests.post(
            OCR_URL,
            headers={
                'Authorization': 'Api-Key ' + Config.YANDEX_API_KEY,
                'Content-Type': 'application/json',
                'x-folder-id': Config.YANDEX_FOLDER_ID,
                'x-data-logging-enabled': 'false',
            },
            json={
                'mimeType': image_type,
                'languageCodes': ['*'],
                'model': 'page',
                'content': base64.b64encode(image).decode('ascii'),
            },
            timeout=20,
        )
        response.raise_for_status()
    except requests.RequestException:
        logger.exception('Vision OCR request failed', extra={'extra_data': {'user_id': user.id}})
        return json_response({'error': 'Receipt recognition failed'}, status_code=502)

    try:
        ocr_text = extract_receipt_text(response.json())
        if not ocr_text:
            return json_response({'receipt': {'total': None, 'currency': None, 'items': []}})
        receipt = parse_receipt(ocr_text)
    except (KeyError, TypeError, ValueError, requests.RequestException):
        logger.exception('Receipt parsing failed', extra={'extra_data': {'user_id': user.id}})
        return json_response({'error': 'Receipt parsing failed'}, status_code=502)
    logger.info('Receipt recognized', extra={'extra_data': {
        'user_id': user.id,
        'item_count': len(receipt['items']),
        'has_total': receipt['total'] is not None,
    }})
    return json_response({'receipt': receipt})

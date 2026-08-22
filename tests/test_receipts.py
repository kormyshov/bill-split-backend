import base64
import json
from unittest.mock import Mock, patch

from handlers.receipts import _normalize_receipt, extract_receipt_text, scan_receipt
from user_orm import UserORM


def _event(payload: dict) -> dict:
    return {'body': base64.b64encode(json.dumps(payload).encode()).decode()}


def _premium_user() -> UserORM:
    return UserORM(1, '123', 'Jane', 'Doe', '2099-01-01', '')


def test_extract_receipt_text_preserves_lines():
    response = {
        'result': {
            'textAnnotation': {
                'blocks': [{'lines': [
                    {'text': 'Milk 2 x 50.00 100.00'},
                    {'text': 'Bread 65,50'},
                    {'text': 'ИТОГО 165,50 ₽'},
                ]}],
            },
        },
    }

    assert extract_receipt_text(response) == 'Milk 2 x 50.00 100.00\nBread 65,50\nИТОГО 165,50 ₽'


@patch('handlers.receipts.requests.post')
@patch('handlers.receipts.Config')
def test_scan_receipt_sends_non_logging_request(config, post):
    config.YANDEX_API_KEY = 'test-key'
    config.YANDEX_FOLDER_ID = 'b1g34n0j9lktsmu9ijjf'
    post.side_effect = [
        Mock(
            json=Mock(return_value={'result': {'textAnnotation': {'blocks': [{'lines': [
                {'text': '寿司 1000'},
                {'text': 'TOTAL 1000 JPY'},
            ]}]}}}),
            raise_for_status=Mock(),
        ),
        Mock(
            json=Mock(return_value={'choices': [{'message': {'content': json.dumps({
                'total': 1000,
                'currency': 'JPY',
                'items': [{'name': '寿司', 'name_en': 'Sushi', 'price': 1000}],
            })}}]}),
            raise_for_status=Mock(),
        ),
    ]

    response = scan_receipt(
        Mock(), _premium_user(), _event({'image_base64': base64.b64encode(b'image').decode()}),
    )

    assert response['statusCode'] == 200
    assert json.loads(response['body']) == {'receipt': {
        'total': 1000.0,
        'currency': 'JPY',
        'items': [{'name': '寿司', 'name_en': 'Sushi', 'price': 1000.0}],
    }}
    assert post.call_count == 2
    ocr_call, parser_call = post.call_args_list
    assert ocr_call.kwargs['headers']['x-data-logging-enabled'] == 'false'
    assert ocr_call.kwargs['headers']['x-folder-id'] == 'b1g34n0j9lktsmu9ijjf'
    assert parser_call.kwargs['headers']['x-data-logging-enabled'] == 'false'
    assert parser_call.kwargs['headers']['OpenAI-Project'] == 'b1g34n0j9lktsmu9ijjf'
    assert parser_call.kwargs['json']['response_format']['type'] == 'json_object'
    parser_prompt = parser_call.kwargs['json']['messages'][0]['content']
    assert 'exactly as it appears in the OCR text into "name"' in parser_prompt
    assert 'English translation in "name_en"' in parser_prompt


def test_normalize_receipt_uses_original_name_when_translation_is_missing():
    receipt = _normalize_receipt({
        'total': 12,
        'currency': 'eur',
        'items': [{'name': '  Wasser  ', 'price': 12}],
    })

    assert receipt['items'] == [{'name': 'Wasser', 'name_en': 'Wasser', 'price': 12.0}]


@patch('handlers.receipts.Config')
def test_scan_receipt_rejects_non_premium_user(config):
    config.YANDEX_API_KEY = 'test-key'
    config.YANDEX_FOLDER_ID = 'folder'

    response = scan_receipt(
        Mock(), UserORM(1, '123', 'Jane', 'Doe', '1900-01-01', ''), _event({}),
    )

    assert response['statusCode'] == 403

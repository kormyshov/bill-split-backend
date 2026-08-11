import base64
import json


def json_response(data: dict, status_code: int = 200) -> dict:
    return {
        'statusCode': status_code,
        'headers': {"Content-Type": "application/json"},
        'body': json.dumps(data),
    }


def decode_body(event: dict) -> str:
    return base64.b64decode(event['body']).decode('utf-8')


def parse_json_body(event: dict) -> dict:
    return json.loads(decode_body(event))

import base64
import json


def json_response(data: dict) -> dict:
    return {
        'statusCode': 200,
        'headers': {"Content-Type": "application/json"},
        'body': json.dumps(data),
    }


def decode_body(event: dict) -> str:
    return base64.b64decode(event['body']).decode('utf-8')


def parse_json_body(event: dict) -> dict:
    return json.loads(decode_body(event))

import json
from unittest.mock import Mock, patch

from abstract_base import UserDoesntExistInDB
from user_orm import UserORM


def test_handler_reuses_user_returned_by_atomic_create():
    created_user = UserORM(1, '12345', 'John', 'Doe', '1900-01-01', '')
    db = Mock()
    db.get_user_info.side_effect = UserDoesntExistInDB
    db.create_user.return_value = created_user
    event = {
        'httpMethod': 'GET',
        'queryStringParameters': {
            'method': 'account/get_info',
            'user_id': 'test',
            'first_name': 'John',
            'last_name': 'Doe',
        },
    }

    with patch('index.Database', return_value=db):
        from index import handler
        response = handler(event, None)

    assert response['statusCode'] == 200
    assert json.loads(response['body']) == {'account': [1, '12345', 'John', 'Doe', '1900-01-01', '']}
    db.get_user_info.assert_called_once_with('test')
    db.create_user.assert_called_once_with('test', 'John', 'Doe')

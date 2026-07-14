import json

import pytest
from unittest.mock import Mock, patch

import ydb

from database import Database
from handlers.rates import update_rates


class MockRow:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class MockResultSet:
    def __init__(self, rows):
        self.rows = rows


class MockTx:
    def __init__(self):
        self.executed = []
        self._return_values = []
        self._return_idx = 0
        self.execute = Mock(side_effect=self._execute_impl)
        self.begin = Mock(return_value=self)

    def _execute_impl(self, query, params=None, commit_tx=True, settings=None):
        self.executed.append((query, params, commit_tx, settings))
        if self._return_idx < len(self._return_values):
            val = self._return_values[self._return_idx]
            self._return_idx += 1
            return val
        return [MockResultSet([])]

    def set_return(self, *values):
        self._return_values = list(values)
        self._return_idx = 0

    def commit(self):
        pass


class MockSession:
    def __init__(self):
        self.transaction_mock = MockTx()

    def transaction(self, *args, **kwargs):
        return self.transaction_mock


class MockPool:
    def __init__(self):
        self.session = MockSession()
        self.retry_calls = []

    def retry_operation_sync(self, func):
        self.retry_calls.append(func)
        return func(self.session)

    def stop(self):
        pass


@pytest.fixture
def mock_driver():
    with patch('database.ydb.Driver') as mock:
        mock_instance = Mock()
        mock_instance.wait = Mock()
        mock.return_value = mock_instance
        yield mock


@pytest.fixture
def mock_pool():
    with patch('database.ydb.SessionPool') as mock:
        pool = MockPool()
        mock.return_value = pool
        yield pool


@pytest.fixture
def db(mock_driver, mock_pool):
    return Database()


FAKE_RATES_RESPONSE = {
    "usd": {"code": "USD", "name": "US Dollar", "rate": "1.0"},
    "eur": {"code": "EUR", "name": "Euro", "rate": "0.92"},
    "gbp": {"code": "GBP", "name": "British Pound", "rate": "0.79"},
}


@patch('handlers.rates.requests.get')
def test_update_rates(mock_get, db):
    mock_response = Mock()
    mock_response.json.return_value = FAKE_RATES_RESPONSE
    mock_get.return_value = mock_response

    with patch.object(db, 'batch_insert_exchange_rates') as mock_batch_insert:
        result = update_rates(db)

        body = json.loads(result['body'])
        assert body == {"ok": True, "updated": 3}

        mock_batch_insert.assert_called_once_with([
            (1, 1.0),
            (2, 0.92),
            (53, 0.79),
        ])


def test_batch_insert_exchange_rates(db, mock_pool):
    db.batch_insert_exchange_rates([(1, 1.0), (2, 0.85)])

    assert len(mock_pool.session.transaction_mock.executed) == 1
    query = mock_pool.session.transaction_mock.executed[0][0]
    assert isinstance(query, ydb.DataQuery)
    assert 'INSERT INTO `exchange_rates`' in query.yql_text
    assert "VALUES" in query.yql_text
    assert ", 1, 1.0)" in query.yql_text
    assert ", 2, 0.85)" in query.yql_text
    assert query.yql_text.count("VALUES") == 1


def make_mock_session(get_latest_result):
    class MockRow:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

    class MockResultSet:
        def __init__(self, rows):
            self.rows = rows

    class MockTx:
        def __init__(self):
            self.execute = Mock(return_value=[MockResultSet(get_latest_result)])

        def begin(self):
            return self

        def commit(self):
            pass

    class MockSession:
        def transaction(self, *args, **kwargs):
            return MockTx()

    return MockSession()


def test_get_rates_success(db):
    rows = [
        MockRow(currency_id=1, rate=1.0),
        MockRow(currency_id=2, rate=0.92),
        MockRow(currency_id=53, rate=0.79),
    ]
    mock_session = make_mock_session(rows)
    db.pool.retry_operation_sync = Mock(return_value=[MockResultSet(rows)])

    result = db.get_latest_exchange_rates(1)

    assert result == [(1, 1.0), (2, 0.92), (53, 0.79)]


def test_get_rates_success_eur(db):
    rows = [
        MockRow(currency_id=1, rate=1.0),
        MockRow(currency_id=2, rate=0.92),
        MockRow(currency_id=53, rate=0.79),
    ]
    db.pool.retry_operation_sync = Mock(return_value=[MockResultSet(rows)])

    result = db.get_latest_exchange_rates(2)

    assert result == [(1, 1.0), (2, 0.92), (53, 0.79)]


def test_get_rates_not_found(db):
    rows = [
        MockRow(currency_id=1, rate=None),
    ]
    db.pool.retry_operation_sync = Mock(return_value=[MockResultSet(rows)])

    result = db.get_latest_exchange_rates(999)

    assert result == []


def test_get_rates_empty_db(db):
    db.pool.retry_operation_sync = Mock(return_value=[MockResultSet([])])

    result = db.get_latest_exchange_rates(1)

    assert result == []


def test_get_rates_handler_usd():
    import base64
    from handlers.rates import get_rates

    def mock_get_latest(currency_id):
        return [(1, 1.0), (2, 0.92), (53, 0.79)]

    db = Mock()
    db.get_latest_exchange_rates = mock_get_latest
    user = Mock()
    body_bytes = json.dumps({'currency_id': 1}).encode('utf-8')
    event = {
        'body': base64.b64encode(body_bytes).decode('utf-8'),
    }

    result = get_rates(db, user, event)
    body = json.loads(result['body'])

    assert body == {
        "rates": {
            "1": 1.0,
            "2": 0.92,
            "53": 0.79,
        }
    }


def test_get_rates_handler_not_found():
    import base64
    from handlers.rates import get_rates

    db = Mock()
    db.get_latest_exchange_rates = Mock(return_value=[])
    user = Mock()
    body_bytes = json.dumps({'currency_id': 999}).encode('utf-8')
    event = {
        'body': base64.b64encode(body_bytes).decode('utf-8'),
    }

    result = get_rates(db, user, event)
    body = json.loads(result['body'])

    assert body == {"rates": {}}

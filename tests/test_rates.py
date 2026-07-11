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


def test_upsert_currency_create(db, mock_pool):
    mock_pool.session.transaction_mock.set_return(
        [MockResultSet([])],                       # SELECT returns nothing
        [MockResultSet([MockRow(id=42)])],         # INSERT returns new id
    )

    result = db.upsert_currency('USD', 'US Dollar')

    assert result == 42

    assert len(mock_pool.session.transaction_mock.executed) == 2
    select_query = mock_pool.session.transaction_mock.executed[0][0]
    assert isinstance(select_query, ydb.DataQuery)
    assert '$symbol' in select_query.yql_text

    insert_query = mock_pool.session.transaction_mock.executed[1][0]
    assert isinstance(insert_query, ydb.DataQuery)
    assert 'INSERT INTO `currencies`' in insert_query.yql_text
    assert 'RETURNING' in insert_query.yql_text


def test_upsert_currency_exists(db, mock_pool):
    mock_pool.session.transaction_mock.set_return(
        [MockResultSet([MockRow(id=7)])],          # SELECT returns existing row
    )

    result = db.upsert_currency('EUR', 'Euro')

    assert result == 7

    assert len(mock_pool.session.transaction_mock.executed) == 1
    select_query = mock_pool.session.transaction_mock.executed[0][0]
    assert isinstance(select_query, ydb.DataQuery)
    assert 'SELECT `id`' in select_query.yql_text


def test_insert_exchange_rate(db, mock_pool):
    db.insert_exchange_rate(1, 0.85)

    assert len(mock_pool.session.transaction_mock.executed) == 1
    query, params, _, _ = mock_pool.session.transaction_mock.executed[0]
    assert isinstance(query, ydb.DataQuery)
    assert 'INSERT INTO `exchange_rates`' in query.yql_text
    assert params['$currency_id'] == 1
    assert params['$rate'] == 0.85
    assert '$created_at' in query.yql_text
    assert params['$created_at'] is not None


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

    with patch.object(db, 'upsert_currency', return_value=1) as mock_upsert, \
         patch.object(db, 'insert_exchange_rate') as mock_insert:
        result = update_rates(db)

        body = json.loads(result['body'])
        assert body == {"ok": True, "updated": 3}

        assert mock_upsert.call_count == 3
        mock_upsert.assert_any_call('USD', 'US Dollar')
        mock_upsert.assert_any_call('EUR', 'Euro')
        mock_upsert.assert_any_call('GBP', 'British Pound')

        assert mock_insert.call_count == 3
        mock_insert.assert_any_call(1, 1.0)
        mock_insert.assert_any_call(1, 0.92)
        mock_insert.assert_any_call(1, 0.79)

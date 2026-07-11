import pytest
from unittest.mock import Mock, MagicMock, patch, PropertyMock
from datetime import datetime

from database import Database
from user_orm import UserORM
from group_orm import GroupORM
from expense_orm import ExpenseORM
from debt_orm import DebtORM
from balance_orm import BalanceORM
from expense_draft import ExpenseDraft
from debt_draft import DebtDraft
from abstract_base import UserDoesntExistInDB

# Import ydb for type checking in tests
import ydb


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
        # YDB returns list of result sets
        return [MockResultSet([])]

    def set_return(self, *values):
        """Set return values for execute calls. Each value should be a list of MockResultSet"""
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


def test_get_user_info_success(db, mock_pool):
        user_data = {
            'id': 1,
            'telegram_id': '12345',
            'first_name': 'John',
            'last_name': 'Doe',
            'expired_date': b'2025-01-01'
        }
        mock_pool.session.transaction_mock.set_return([MockResultSet([MockRow(**user_data)])])

        result = db.get_user_info('12345')

        assert result.id == 1
        assert result.telegram_id == '12345'
        assert result.first_name == 'John'
        assert result.last_name == 'Doe'
        assert result.expired_date == '2025-01-01'

        query, params, _, _ = mock_pool.session.transaction_mock.executed[0]
        assert '$telegram_id' in query
        assert params == {'$telegram_id': '12345'}


def test_get_user_info_not_found(db, mock_pool):
        mock_pool.session.transaction_mock.set_return([MockResultSet([])])

        with pytest.raises(UserDoesntExistInDB):
            db.get_user_info('nonexistent')


def test_create_user(db, mock_pool):
        db.create_user('12345', 'John', 'Doe')

        query, params, _, _ = mock_pool.session.transaction_mock.executed[0]
        assert 'INSERT INTO `users`' in query
        assert params == {
            '$telegram_id': '12345',
            '$first_name': 'John',
            '$last_name': 'Doe',
        }


def test_get_group_list(db, mock_pool):
        user = UserORM(1, '12345', 'John', 'Doe', '2025-01-01')
        group_data = {
            'id': 1,
            'created_at': '2024-01-01 12:00:00',
            'created_by': 1,
            'name': 'Test Group',
            'count': 3,
            'token': b'abc123'
        }
        mock_pool.session.transaction_mock.set_return([MockResultSet([MockRow(**group_data)])])

        result = db.get_group_list(user)

        assert len(result) == 1
        assert isinstance(result[0], GroupORM)
        assert result[0].name == 'Test Group'

        query, params, _, _ = mock_pool.session.transaction_mock.executed[0]
        assert '$user_id' in query
        assert params == {'$user_id': 1}


def test_create_group(db, mock_pool):
        user = UserORM(1, '12345', 'John', 'Doe', '2025-01-01')
        group_result = MockRow(id=42)
        mock_pool.session.transaction_mock.set_return(
            [MockResultSet([group_result])],  # First execute: returns list of result sets
            [MockResultSet([])]               # Second execute
        )

        db.create_group(user, 'New Group')

        assert len(mock_pool.session.transaction_mock.executed) == 2
        query1, params1, _, _ = mock_pool.session.transaction_mock.executed[0]
        assert 'INSERT INTO `groups`' in query1
        assert params1['$name'] == 'New Group'
        assert params1['$created_by'] == 1

        query2, params2, _, _ = mock_pool.session.transaction_mock.executed[1]
        assert 'INSERT INTO `group_members`' in query2
        assert params2['$group_id'] == 42
        assert params2['$user_id'] == 1


def test_change_group_name(db, mock_pool):
        db.change_group_name(1, 'New Name', '2024-01-01 12:00:00', 1)

        query, params, _, _ = mock_pool.session.transaction_mock.executed[0]
        assert 'UPSERT INTO `groups`' in query
        assert params == {
            '$group_id': 1,
            '$name': 'New Name',
            '$created_at': '2024-01-01 12:00:00',
            '$created_by': 1,
        }


def test_get_group_member_list(db, mock_pool):
        member_data = {
            'id': 2,
            'telegram_id': '67890',
            'first_name': 'Jane',
            'last_name': 'Smith'
        }
        mock_pool.session.transaction_mock.set_return([MockResultSet([MockRow(**member_data)])])

        result = db.get_group_member_list(1)

        assert len(result) == 1
        assert result[0].first_name == 'Jane'

        query, params, _, _ = mock_pool.session.transaction_mock.executed[0]
        assert '$group_id' in query
        assert params == {'$group_id': 1}


def test_join_to_group(db, mock_pool):
        user = UserORM(1, '12345', 'John', 'Doe', '2025-01-01')
        db.join_to_group(user, 'token123')

        query, params, _, _ = mock_pool.session.transaction_mock.executed[0]
        assert '$group_token' in query
        assert '$user_id' in query
        assert params == {
            '$group_token': 'token123',
            '$user_id': 1,
        }


def test_leave_group(db, mock_pool):
        user = UserORM(1, '12345', 'John', 'Doe', '2025-01-01')
        db.leave_group(user, 1)

        query, params, _, _ = mock_pool.session.transaction_mock.executed[0]
        assert 'DELETE FROM `group_members`' in query
        assert params == {
            '$group_id': 1,
            '$user_id': 1,
        }


def test_get_group_expense_list(db, mock_pool):
        user = UserORM(1, '12345', 'John', 'Doe', '2025-01-01')
        expense_data = {
            'id': 1,
            'name': 'Dinner',
            'created_at': '2024-01-01 12:00:00',
            'first_and_last_name': b'John Doe',
            'amount': 1000,
            'currency_symbol': b'$',
            'debt_amount': 500
        }
        mock_pool.session.transaction_mock.set_return([MockResultSet([MockRow(**expense_data)])])

        result = db.get_group_expense_list(user, 1)

        assert len(result) == 1
        assert isinstance(result[0], ExpenseORM)
        assert result[0].name == 'Dinner'

        query, params, _, _ = mock_pool.session.transaction_mock.executed[0]
        assert '$group_id' in query
        assert '$user_id' in query
        assert params == {
            '$group_id': 1,
            '$user_id': 1,
        }


def test_get_expense_debt_list(db, mock_pool):
        debt_data = {
            'id': 1,
            'expense_name': 'Dinner',
            'created_at': '2024-01-01 12:00:00',
            'total_amount': 1000,
            'currency_symbol': b'$',
            'paid_by_first_and_last_name': b'John Doe',
            'debt_amount': 500,
            'first_and_last_name': b'Jane Smith'
        }
        mock_pool.session.transaction_mock.set_return([MockResultSet([MockRow(**debt_data)])])

        result = db.get_expense_debt_list(1)

        assert len(result) == 1
        assert isinstance(result[0], DebtORM)

        query, params, _, _ = mock_pool.session.transaction_mock.executed[0]
        assert '$expense_id' in query
        assert params == {'$expense_id': 1}


def test_create_payment(db, mock_pool):
        import ydb
        expense = ExpenseDraft(
            user_id=1,
            amount=1000,
            currency_id=1,
            debts=[DebtDraft(2, 500), DebtDraft(3, 500)]
        )
        expense_id_result = MockRow(id=42)
        mock_pool.session.transaction_mock.set_return(
            [MockResultSet([expense_id_result])],
            [MockResultSet([])],
            [MockResultSet([])]
        )

        db.create_payment(1, expense, 'Dinner')

        assert len(mock_pool.session.transaction_mock.executed) == 3

        query1, params1, commit_tx1, _ = mock_pool.session.transaction_mock.executed[0]
        assert 'INSERT INTO `expenses`' in query1
        assert commit_tx1 is False
        assert params1['$name'] == 'Dinner'
        assert params1['$paid_by'] == 1
        assert params1['$amount'] == 1000
        assert params1['$currency'] == 1

        query2, params2, commit_tx2, _ = mock_pool.session.transaction_mock.executed[1]
        assert 'INSERT INTO `debts`' in query2
        assert commit_tx2 is False
        assert params2['$expense_id'] == 42
        assert params2['$user_id'] == 2
        assert params2['$amount'] == 500


def test_delete_expense(db, mock_pool):
        import ydb
        db.delete_expense(1)

        query, params, _, _ = mock_pool.session.transaction_mock.executed[0]
        assert 'DELETE FROM `expenses`' in query
        assert 'DELETE FROM `debts`' in query
        assert params == {'$expense_id': 1}


def test_get_group_balance_list(db, mock_pool):
        import ydb
        user = UserORM(1, '12345', 'John', 'Doe', '2025-01-01')
        balance_data = {
            'user_id': 2,
            'currency': 1,
            'amount': 500,
            'currency_symbol': b'$',
            'first_and_last_name': b'Jane Smith'
        }
        mock_pool.session.transaction_mock.set_return([MockResultSet([MockRow(**balance_data)])])

        result = db.get_group_balance_list(user, 1)

        assert len(result) == 1
        assert isinstance(result[0], BalanceORM)
        assert result[0].amount == 500

        query, params, _, _ = mock_pool.session.transaction_mock.executed[0]
        assert '$group_id' in query
        assert '$user_id' in query
        assert params == {
            '$group_id': 1,
            '$user_id': 1,
        }


def test_paid_premium(db, mock_pool):
        import ydb
        user = UserORM(1, '12345', 'John', 'Doe', '2025-01-01')
        db.paid_premium(user, '2026-01-01')

        query, params, _, _ = mock_pool.session.transaction_mock.executed[0]
        assert 'UPSERT INTO `users`' in query
        assert params == {
            '$user_id': 1,
            '$telegram_id': '12345',
            '$first_name': 'John',
            '$last_name': 'Doe',
            '$expired_date': '2026-01-01',
        }


def test_all_queries_use_parameters_not_format(db):
    import inspect
    source = inspect.getsource(Database)
    assert '.format(' not in source
    assert '$' in source  # has parameter placeholders
    assert 'parameters=' not in source  # uses positional dict not keyword


def test_all_parameterized_queries_have_declare(db):
    """Ensure every query using $params has DECLARE statements."""
    import inspect
    import re

    source = inspect.getsource(Database)

    # Find all execute() calls with their query strings
    # Pattern: execute(""" ... """, {params})
    execute_calls = re.findall(
        r'execute\(\s*("""[\s\S]*?""")\s*,\s*\{[^}]+\}',
        source
    )

    assert len(execute_calls) > 0, "No execute calls found"

    for query in execute_calls:
        # Extract parameter names used in query
        params_in_query = set(re.findall(r'\$(\w+)', query))
        if not params_in_query:
            continue  # Query without parameters is fine

        # Parameters that are assigned within the query (e.g., `$var = SELECT...`)
        # don't need DECLARE
        assigned_vars = set(re.findall(r'\$(\w+)\s*=', query))

        # Check for DECLARE statements for each parameter (excluding assigned vars)
        for param in params_in_query:
            if param in assigned_vars:
                continue
            declare_pattern = rf'DECLARE\s+\${param}\s+AS\s+\w+'
            assert re.search(declare_pattern, query), \
                f"Missing DECLARE for ${param} in query:\n{query[:200]}..."
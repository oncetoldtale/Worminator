import unittest
from unittest.mock import AsyncMock, patch

from tests.support.dependency_stubs import install_test_environment
from tests.support.db_fakes import FakeConnection, FakePool


install_test_environment()

import postgres


class PostgresTests(unittest.IsolatedAsyncioTestCase):
    async def test_CreatePool_WhenCalled_ShouldCreateAsyncpgPoolWithConfiguredSettings(self):
        pool = object()

        with patch("postgres.asyncpg.create_pool", new=AsyncMock(return_value=pool), create=True) as create_pool:
            result = await postgres.create_pool()

        self.assertIs(result, pool)
        create_pool.assert_awaited_once_with(
            user=postgres.DB_USER,
            password=postgres.DB_PASSWORD,
            database=postgres.DB_DATABASE,
            host=postgres.DB_HOST,
            port=postgres.DB_PORT,
            min_size=1,
            max_size=10,
            command_timeout=10,
            timeout=10,
        )

    async def test_GetConn_WhenWrappedFunctionRaises_ShouldReraiseException(self):
        expected_error = RuntimeError("database failure")

        @postgres.get_conn
        async def failing_query(connection):
            raise expected_error

        with self.assertRaisesRegex(RuntimeError, "database failure"):
            await failing_query(FakePool(FakeConnection()))

    async def test_GetAllTickets_WhenRowsExist_ShouldReturnUserTicketMapping(self):
        connection = FakeConnection()
        connection.fetch_rows = [
            {"user_id": 1, "ticket_count": 4},
            {"user_id": 2, "ticket_count": 0},
        ]

        tickets = await postgres.get_all_tickets(FakePool(connection))

        self.assertEqual(tickets, {1: 4, 2: 0})

    async def test_GetUserTickets_WhenUserMissing_ShouldReturnZero(self):
        connection = FakeConnection()
        connection.fetchrow_result = None

        tickets = await postgres.get_user_tickets(FakePool(connection), 1)

        self.assertEqual(tickets, 0)

    async def test_GetUserTickets_WhenUserExists_ShouldReturnTicketCount(self):
        connection = FakeConnection()
        connection.fetchrow_result = {"ticket_count": 7}

        tickets = await postgres.get_user_tickets(FakePool(connection), 1)

        self.assertEqual(tickets, 7)

    async def test_UpdateUserTickets_WhenUsersProvided_ShouldUpsertTicketCredits(self):
        connection = FakeConnection()

        await postgres.update_user_tickets(
            FakePool(connection),
            [(1, "alice"), (2, "bob")],
            5,
        )

        self.assertEqual(len(connection.executemany_calls), 1)
        query, values = connection.executemany_calls[0]
        self.assertIn("ON CONFLICT (user_id)", query)
        self.assertIn("ticket_count = users.ticket_count + EXCLUDED.ticket_count", query)
        self.assertEqual(values, [(1, "alice", 5), (2, "bob", 5)])

    async def test_SetUserTicketsZero_WhenUsersProvided_ShouldResetExistingTickets(self):
        connection = FakeConnection()

        await postgres.set_user_tickets_zero(
            FakePool(connection),
            [(1, "alice"), (2, "bob")],
        )

        self.assertEqual(len(connection.executemany_calls), 1)
        query, values = connection.executemany_calls[0]
        self.assertIn("SET ticket_count = 0", query)
        self.assertEqual(values, [(1, "alice"), (2, "bob")])

    async def test_ResolveRaffleTickets_WhenWinnerAndUsersToCredit_ShouldExecuteInSingleTransaction(self):
        connection = FakeConnection()

        await postgres.resolve_raffle_tickets(
            FakePool(connection),
            (1, "alice"),
            [(2, "bob"), (3, "cora")],
            2,
        )

        self.assertTrue(connection.transaction_context.entered)
        self.assertTrue(connection.transaction_context.exited)
        self.assertEqual(len(connection.operations), 1)
        operation, query, args = connection.operations[0]
        self.assertEqual(operation, "execute")
        self.assertIn("times_coached = users.times_coached + 1", query)
        self.assertEqual(args, (1, "alice"))
        self.assertEqual(len(connection.executemany_calls), 1)
        _, values = connection.executemany_calls[0]
        self.assertEqual(values, [(2, "bob", 2), (3, "cora", 2)])

    async def test_ResolveRaffleTickets_WhenNoWinner_ShouldOnlyCreditParticipants(self):
        connection = FakeConnection()

        await postgres.resolve_raffle_tickets(
            FakePool(connection),
            None,
            [(2, "bob")],
            3,
        )

        self.assertEqual(connection.operations, [])
        self.assertEqual(len(connection.executemany_calls), 1)
        _, values = connection.executemany_calls[0]
        self.assertEqual(values, [(2, "bob", 3)])

    async def test_DebugCreateNewTables_WhenCalled_ShouldExecuteUsersTableDdl(self):
        connection = FakeConnection()

        await postgres.debug_create_new_tables(FakePool(connection))

        self.assertEqual(len(connection.operations), 1)
        operation, query, args = connection.operations[0]
        self.assertEqual(operation, "execute")
        self.assertEqual(args, ())
        self.assertIn("DROP TABLE IF EXISTS users", query)
        self.assertIn("CREATE TABLE users", query)
        self.assertIn("times_coached", query)

    async def test_DebugDropAllTables_WhenCalled_ShouldDropUsersTable(self):
        connection = FakeConnection()

        await postgres.debug_drop_all_tables(FakePool(connection))

        self.assertEqual(connection.operations, [("execute", "DROP TABLE IF EXISTS users;", ())])

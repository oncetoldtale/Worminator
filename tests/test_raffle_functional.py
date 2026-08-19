import unittest
from unittest.mock import AsyncMock, patch

import raffle as raffle_module
from raffle import Raffle
from tests.support.dependency_stubs import install_test_environment
from tests.support.fakes import FakeBot, MessageRecorder

install_test_environment()


class RaffleFunctionalTests(unittest.IsolatedAsyncioTestCase):
    async def test_RaffleFlow_WhenEntriesAndClaimsResolveWinner_ShouldRecordWinnerAndCreditLosersAndClaimers(self):
        raffle = Raffle(ticket_amt=1)
        raffle.open = True
        raffle.bot = FakeBot()
        raffle.pool = object()
        messages = MessageRecorder()

        await raffle.enter(1, "alice", messages)
        await raffle.enter(2, "bob", messages)
        await raffle.claim(3, "cora", messages)

        with patch.object(raffle, "draw", new=AsyncMock(return_value=(1, "alice"))):
            await raffle.close(messages, raffle.pool)

        await raffle.resolve(messages)

        self.assertEqual(raffle.bot.winners, [1])
        self.assertEqual(len(raffle.bot.db_calls), 1)
        func, args = raffle.bot.db_calls[0]
        self.assertIs(func, raffle_module.postgres.resolve_raffle_tickets)
        self.assertEqual(args, (raffle.pool, (1, "alice"), [(2, "bob"), (3, "cora")], 1))

    async def test_RaffleFlow_WhenWinnerResolved_ShouldRecordWinnerAndCreditLosers(self):
        raffle = Raffle(ticket_amt=1)
        raffle.open = True
        raffle.bot = FakeBot()
        raffle.pool = object()
        messages = MessageRecorder()

        await raffle.enter(1, "alice", messages)
        await raffle.enter(2, "bob", messages)

        with patch.object(raffle, "draw", new=AsyncMock(return_value=(1, "alice"))):
            await raffle.close(messages, raffle.pool)

        await raffle.resolve(messages)

        self.assertEqual(raffle.bot.winners, [1])
        self.assertEqual(len(raffle.bot.db_calls), 1)
        func, args = raffle.bot.db_calls[0]
        self.assertIs(func, raffle_module.postgres.resolve_raffle_tickets)
        self.assertEqual(args, (raffle.pool, (1, "alice"), [(2, "bob")], 1))

    async def test_RaffleFlow_WhenClaimOnlyUserResolved_ShouldCreditClaimedTicket(self):
        raffle = Raffle(ticket_amt=2)
        raffle.open = True
        raffle.bot = FakeBot()
        raffle.pool = object()
        messages = MessageRecorder()

        await raffle.claim(1, "alice", messages)
        await raffle.resolve(messages)

        self.assertEqual(raffle.bot.winners, [])
        self.assertEqual(messages.messages[-1], "No winner, tickets awarded to all participants.")
        func, args = raffle.bot.db_calls[0]
        self.assertIs(func, raffle_module.postgres.resolve_raffle_tickets)
        self.assertEqual(args, (raffle.pool, None, [(1, "alice")], 2))

    async def test_RaffleFlow_WhenWinnerRedrawnAndNoEntriesRemain_ShouldCreditClaimersAndRedrawnWinner(self):
        raffle = Raffle(ticket_amt=1)
        raffle.open = True
        raffle.bot = FakeBot()
        raffle.pool = object()
        messages = MessageRecorder()

        await raffle.enter(1, "alice", messages)
        await raffle.claim(2, "bob", messages)

        with patch.object(raffle, "draw", new=AsyncMock(return_value=(1, "alice"))):
            await raffle.close(messages, raffle.pool)

        await raffle.redraw(messages, raffle.pool)
        await raffle.resolve(messages)

        self.assertIsNone(raffle.current_winner)
        self.assertEqual(raffle.users["Redrawn"], {1: "alice"})
        func, args = raffle.bot.db_calls[0]
        self.assertIs(func, raffle_module.postgres.resolve_raffle_tickets)
        self.assertEqual(args, (raffle.pool, None, [(2, "bob"), (1, "alice")], 1))

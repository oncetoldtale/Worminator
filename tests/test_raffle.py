import unittest
from unittest.mock import AsyncMock, patch

from tests.support.dependency_stubs import install_test_environment
from tests.support.fakes import FakeBot, FakeTask, MessageRecorder


install_test_environment()

import raffle as raffle_module
from raffle import Raffle


class RaffleTests(unittest.IsolatedAsyncioTestCase):
    def test_Cancel_WhenRaffleHasRunningTask_ShouldCloseRaffleAndCancelTask(self):
        raffle = Raffle()
        task = FakeTask()
        raffle.open = True
        raffle.task = task

        raffle.cancel()

        self.assertFalse(raffle.open)
        self.assertTrue(task.cancelled)

    def test_Extend_WhenRaffleHasRunningTask_ShouldCancelCurrentTimerAndStartNewTimerWithPool(self):
        raffle = Raffle(duration=10)
        current_task = FakeTask()
        new_task = FakeTask()
        messages = MessageRecorder()
        pool = object()
        timer_calls = []
        raffle.task = current_task
        raffle.send_message = messages
        raffle.pool = pool

        def fake_timer(send_message, timer_pool):
            timer_calls.append((send_message, timer_pool))
            return object()

        with patch.object(raffle, "_run_timer", new=fake_timer), \
             patch("raffle.asyncio.create_task", return_value=new_task):
            raffle.extend(30)

        self.assertTrue(current_task.cancelled)
        self.assertEqual(raffle.duration, 30)
        self.assertEqual(timer_calls, [(messages, pool)])
        self.assertIs(raffle.task, new_task)

    async def test_Enter_WhenNoRaffleOpen_ShouldNotifyUser(self):
        raffle = Raffle()
        raffle.bot = FakeBot()
        messages = MessageRecorder()

        await raffle.enter(1, "alice", messages)

        self.assertEqual(messages.messages, ["alice, no raffle is open!"])
        self.assertEqual(raffle.users["Entries"], {})

    async def test_Enter_WhenUserAlreadyEntered_ShouldNotDuplicateEntry(self):
        raffle = Raffle()
        raffle.open = True
        raffle.bot = FakeBot()
        raffle.users["Entries"][1] = "alice"
        messages = MessageRecorder()

        await raffle.enter(1, "alice", messages)

        self.assertEqual(messages.messages, ["alice, you have already entered the raffle!"])
        self.assertEqual(raffle.users["Entries"], {1: "alice"})

    async def test_Enter_WhenUserAlreadyWon_ShouldSuggestClaimInstead(self):
        raffle = Raffle()
        raffle.open = True
        raffle.bot = FakeBot()
        raffle.bot.winners.append(1)
        messages = MessageRecorder()

        await raffle.enter(1, "alice", messages)

        self.assertEqual(
            messages.messages,
            ["alice, you have already WON a raffle this session, please !claim instead!"],
        )
        self.assertEqual(raffle.users["Entries"], {})

    async def test_Enter_WhenUserHasClaimed_ShouldMoveUserToEntries(self):
        raffle = Raffle()
        raffle.open = True
        raffle.bot = FakeBot()
        raffle.users["Claims"][1] = "alice"
        messages = MessageRecorder()

        await raffle.enter(1, "alice", messages)

        self.assertEqual(raffle.users["Claims"], {})
        self.assertEqual(raffle.users["Entries"], {1: "alice"})
        self.assertEqual(messages.messages, ["alice, you have been moved into the raffle!"])

    async def test_Claim_WhenUserHasEntered_ShouldMoveUserToClaims(self):
        raffle = Raffle()
        raffle.open = True
        raffle.users["Entries"][1] = "alice"
        messages = MessageRecorder()

        await raffle.claim(1, "alice", messages)

        self.assertEqual(raffle.users["Entries"], {})
        self.assertEqual(raffle.users["Claims"], {1: "alice"})
        self.assertEqual(
            messages.messages,
            ["alice, you have claimed your ticket and have been removed from the raffle!"],
        )

    async def test_Claim_WhenUserAlreadyClaimed_ShouldNotDuplicateClaim(self):
        raffle = Raffle()
        raffle.open = True
        raffle.users["Claims"][1] = "alice"
        messages = MessageRecorder()

        await raffle.claim(1, "alice", messages)

        self.assertEqual(raffle.users["Claims"], {1: "alice"})
        self.assertEqual(messages.messages, ["alice, you have already claimed your ticket!"])

    async def test_Draw_WhenTicketsLoaded_ShouldUseTicketCountsAsWeights(self):
        raffle = Raffle()
        raffle.users["Entries"] = {1: "alice", 2: "bob"}
        pool = object()

        with patch("raffle.postgres.get_all_tickets", new=AsyncMock(return_value={1: 5, 2: 1})), \
             patch("raffle.random.choices", return_value=[(1, "alice")]) as choices:
            winner = await raffle.draw(pool)

        self.assertEqual(winner, (1, "alice"))
        choices.assert_called_once_with([(1, "alice"), (2, "bob")], weights=[5, 1], k=1)

    async def test_Close_WhenNoEntries_ShouldCloseWithoutWinner(self):
        raffle = Raffle()
        raffle.open = True
        messages = MessageRecorder()

        await raffle.close(messages, object())

        self.assertFalse(raffle.open)
        self.assertIsNone(raffle.current_winner)
        self.assertEqual(messages.messages, ["No entries. Raffle closed."])

    async def test_Redraw_WhenNoActiveWinner_ShouldNotifyUser(self):
        raffle = Raffle()
        messages = MessageRecorder()

        await raffle.redraw(messages, object())

        self.assertEqual(messages.messages, ["No active winner to redraw."])

    async def test_Redraw_WhenNoEligibleEntriesRemain_ShouldMoveWinnerToRedrawnAndClearWinner(self):
        raffle = Raffle()
        raffle.current_winner = (1, "alice")
        raffle.users["Entries"] = {1: "alice"}
        messages = MessageRecorder()

        await raffle.redraw(messages, object())

        self.assertIsNone(raffle.current_winner)
        self.assertEqual(raffle.users["Entries"], {})
        self.assertEqual(raffle.users["Redrawn"], {1: "alice"})
        self.assertEqual(messages.messages, ["No eligible entries remaining to redraw from."])

    async def test_Resolve_WhenWinnerExists_ShouldResetWinnerAndCreditLosersClaimersAndRedrawn(self):
        raffle = Raffle(ticket_amt=2)
        raffle.bot = FakeBot()
        raffle.pool = object()
        raffle.current_winner = (1, "alice")
        raffle.users["Entries"] = {1: "alice", 2: "bob"}
        raffle.users["Claims"] = {3: "cora"}
        raffle.users["Redrawn"] = {4: "dan"}
        messages = MessageRecorder()

        await raffle.resolve(messages)

        self.assertEqual(raffle.bot.winners, [1])
        self.assertEqual(messages.messages, [])
        self.assertEqual(len(raffle.bot.db_calls), 1)
        func, args = raffle.bot.db_calls[0]
        self.assertIs(func, raffle_module.postgres.resolve_raffle_tickets)
        self.assertEqual(args, (raffle.pool, (1, "alice"), [(2, "bob"), (3, "cora"), (4, "dan")], 2))

    async def test_Resolve_WhenNoWinnerButParticipantsExist_ShouldCreditEveryone(self):
        raffle = Raffle(ticket_amt=3)
        raffle.bot = FakeBot()
        raffle.pool = object()
        raffle.users["Entries"] = {1: "alice"}
        raffle.users["Claims"] = {2: "bob"}
        raffle.users["Redrawn"] = {3: "cora"}
        messages = MessageRecorder()

        await raffle.resolve(messages)

        self.assertEqual(messages.messages, ["No winner, tickets awarded to all participants."])
        func, args = raffle.bot.db_calls[0]
        self.assertIs(func, raffle_module.postgres.resolve_raffle_tickets)
        self.assertEqual(args, (raffle.pool, None, [(1, "alice"), (2, "bob"), (3, "cora")], 3))

    async def test_Resolve_WhenNoWinnerAndNoParticipants_ShouldNotIssueTickets(self):
        raffle = Raffle()
        raffle.bot = FakeBot()
        raffle.pool = object()
        messages = MessageRecorder()

        await raffle.resolve(messages)

        self.assertEqual(messages.messages, ["No active winner and no entries. No tickets issued."])
        self.assertEqual(raffle.bot.db_calls, [])

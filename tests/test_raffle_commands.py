import unittest
from unittest.mock import AsyncMock, Mock, patch

import raffle as raffle_module
from raffle import Raffle
from tests.support.dependency_stubs import install_test_environment
from tests.support.fakes import FakeBot, FakeCommand, FakeTask

install_test_environment()


class RaffleCommandTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        raffle_module.raffle = None
        self.original_superadmin_id = raffle_module.SUPERADMIN_ID
        raffle_module.SUPERADMIN_ID = 123

    def tearDown(self):
        current_raffle = raffle_module.raffle
        if current_raffle and current_raffle.task:
            current_raffle.task.cancel()
        raffle_module.raffle = None
        raffle_module.SUPERADMIN_ID = self.original_superadmin_id

    async def test_UserIsSuperadmin_WhenCommandUserIdIsString_ShouldAuthorizeMatchingIntegerId(self):
        command = FakeCommand(user_id="123")

        is_superadmin = raffle_module.user_is_superadmin(command)

        self.assertTrue(is_superadmin)

    async def test_NewRaffleCommand_WhenExistingRaffleUnresolved_ShouldAskToResolveFirst(self):
        bot = FakeBot()
        raffle_module.raffle = Raffle()
        command = FakeCommand(parameter="10")
        commands = raffle_module.make_commands(bot)

        await commands["newraffle"](command)

        self.assertEqual(command.replies, ["Please resolve the current raffle first!"])

    async def test_NewRaffleCommand_WhenDurationInvalid_ShouldRejectInput(self):
        bot = FakeBot()
        command = FakeCommand(parameter="abc")
        commands = raffle_module.make_commands(bot)

        await commands["newraffle"](command)

        self.assertEqual(command.replies, ["Please input a valid duration (int)."])
        self.assertIsNone(raffle_module.raffle)

    async def test_AddTicketCommand_WhenTwitchUserUnresolved_ShouldNotUpdateDatabase(self):
        bot = FakeBot()
        command = FakeCommand(parameter="missing_user 5")
        commands = raffle_module.make_commands(bot)

        with patch("raffle.get_twitch_user_id", new=AsyncMock(return_value=None)):
            await commands["addticket"](command)

        self.assertEqual(command.replies, ["Could not find Twitch user: missing_user"])
        self.assertEqual(bot.db_calls, [])

    async def test_AddTicketCommand_WhenInputInvalid_ShouldReplyWithUsage(self):
        bot = FakeBot()
        commands = raffle_module.make_commands(bot)
        usage = "Usage: !addticket <USERNAME> [ticket_amt|1]"

        for parameter in ("", "alice abc", "alice 5 extra"):
            with self.subTest(parameter=parameter):
                command = FakeCommand(parameter=parameter)
                await commands["addticket"](command)
                self.assertEqual(command.replies, [usage])
                self.assertEqual(bot.db_calls, [])

    async def test_MyTicketsCommand_WhenTwitchUserUnresolved_ShouldNotReadDatabase(self):
        bot = FakeBot()
        command = FakeCommand(user_id=7, name="viewer")
        commands = raffle_module.make_commands(bot)

        with patch("raffle.get_twitch_user_id", new=AsyncMock(return_value=None)):
            await commands["mytickets"](command)

        self.assertEqual(command.replies, ["Could not resolve your Twitch account."])
        self.assertEqual(bot.db_calls, [])

    async def test_NewRaffleCommand_WhenUserIsNotSuperadmin_ShouldNotCreateRaffle(self):
        bot = FakeBot()
        command = FakeCommand(user_id=999, name="viewer", parameter="10")
        commands = raffle_module.make_commands(bot)

        await commands["newraffle"](command)

        self.assertEqual(command.replies, [])
        self.assertIsNone(raffle_module.raffle)

    async def test_AddTicketCommand_WhenUserIsNotSuperadmin_ShouldNotUpdateDatabase(self):
        bot = FakeBot()
        command = FakeCommand(user_id=999, name="viewer", parameter="alice 5")
        commands = raffle_module.make_commands(bot)

        await commands["addticket"](command)

        self.assertEqual(command.replies, [])
        self.assertEqual(bot.db_calls, [])

    async def test_EnterCommand_WhenNoRaffleOpen_ShouldNotifyUser(self):
        bot = FakeBot()
        command = FakeCommand(user_id=7, name="viewer")
        commands = raffle_module.make_commands(bot)

        await commands["enter"](command)

        self.assertEqual(command.replies, ["There is no raffle open right now!"])

    async def test_ClaimCommand_WhenNoRaffleOpen_ShouldNotifyUser(self):
        bot = FakeBot()
        command = FakeCommand(user_id=7, name="viewer")
        commands = raffle_module.make_commands(bot)

        await commands["claim"](command)

        self.assertEqual(command.replies, ["There is no raffle open right now!"])

    async def test_CancelCommand_WhenRaffleExists_ShouldCancelAndClearRaffle(self):
        bot = FakeBot()
        command = FakeCommand()
        active_raffle = Raffle()
        raffle_module.raffle = active_raffle
        commands = raffle_module.make_commands(bot)

        await commands["cancel"](command)

        self.assertIsNone(raffle_module.raffle)
        self.assertFalse(active_raffle.open)
        self.assertEqual(command.replies, ["Raffle has been cancelled."])

    async def test_AddTicketCommand_WhenTwitchUserResolved_ShouldUpdateDatabase(self):
        bot = FakeBot()
        command = FakeCommand(parameter="alice 5")
        commands = raffle_module.make_commands(bot)

        with patch("raffle.get_twitch_user_id", new=AsyncMock(return_value=77)):
            await commands["addticket"](command)

        self.assertEqual(command.replies, ["Added 5 ticket(s) to alice!"])
        self.assertEqual(len(bot.db_calls), 1)
        func, args = bot.db_calls[0]
        self.assertIs(func, raffle_module.postgres.update_user_tickets)
        self.assertEqual(args, (bot.pool, [(77, "alice")], 5))

    async def test_AddTicketCommand_WhenTicketAmountOmitted_ShouldDefaultToOne(self):
        bot = FakeBot()
        command = FakeCommand(parameter="alice")
        commands = raffle_module.make_commands(bot)

        with patch("raffle.get_twitch_user_id", new=AsyncMock(return_value=77)):
            await commands["addticket"](command)

        self.assertEqual(command.replies, ["Added 1 ticket(s) to alice!"])
        self.assertEqual(len(bot.db_calls), 1)
        func, args = bot.db_calls[0]
        self.assertIs(func, raffle_module.postgres.update_user_tickets)
        self.assertEqual(args, (bot.pool, [(77, "alice")], 1))

    async def test_MyTicketsCommand_WhenTwitchUserResolved_ShouldReadDatabase(self):
        bot = FakeBot()
        command = FakeCommand(user_id=7, name="viewer")
        commands = raffle_module.make_commands(bot)

        async def queue_db(func, *args):
            bot.db_calls.append((func, args))
            return 4

        bot.queue_db = queue_db
        with patch("raffle.get_twitch_user_id", new=AsyncMock(return_value=7)):
            await commands["mytickets"](command)

        self.assertEqual(command.replies, ["viewer, you have 4 ticket(s)."])
        func, args = bot.db_calls[0]
        self.assertIs(func, raffle_module.postgres.get_user_tickets)
        self.assertEqual(args, (bot.pool, 7))

    async def test_ExtendCommand_WhenRaffleOpen_ShouldExtendRaffleAndReply(self):
        bot = FakeBot()
        command = FakeCommand(parameter="30")
        active_raffle = Raffle()
        active_raffle.open = True
        active_raffle.extend = Mock()
        raffle_module.raffle = active_raffle
        commands = raffle_module.make_commands(bot)

        await commands["extend"](command)

        active_raffle.extend.assert_called_once_with(30)
        self.assertEqual(command.replies, ["Raffle extended by 30 seconds!"])

    async def test_ExtendCommand_WhenNoRaffleOpen_ShouldNotifyUser(self):
        bot = FakeBot()
        command = FakeCommand(parameter="30")
        commands = raffle_module.make_commands(bot)

        await commands["extend"](command)

        self.assertEqual(command.replies, ["There is no raffle open right now!"])

    async def test_ExtendCommand_WhenInputInvalid_ShouldRejectInput(self):
        bot = FakeBot()
        command = FakeCommand(parameter="abc")
        active_raffle = Raffle()
        active_raffle.open = True
        active_raffle.extend = Mock()
        raffle_module.raffle = active_raffle
        commands = raffle_module.make_commands(bot)

        await commands["extend"](command)

        active_raffle.extend.assert_not_called()
        self.assertEqual(command.replies, ["Please input a valid duration (int)."])

    async def test_ClearCommand_WhenRaffleExists_ShouldClearEntriesAndClaims(self):
        bot = FakeBot()
        command = FakeCommand()
        active_raffle = Raffle()
        active_raffle.users["Entries"] = {1: "alice"}
        active_raffle.users["Claims"] = {2: "bob"}
        raffle_module.raffle = active_raffle
        commands = raffle_module.make_commands(bot)

        await commands["clear"](command)

        self.assertEqual(active_raffle.users["Entries"], {})
        self.assertEqual(active_raffle.users["Claims"], {})
        self.assertEqual(command.replies, ["Raffle entries and claims have been cleared."])

    async def test_ClearCommand_WhenNoRaffleExists_ShouldNotifyUser(self):
        bot = FakeBot()
        command = FakeCommand()
        commands = raffle_module.make_commands(bot)

        await commands["clear"](command)

        self.assertEqual(command.replies, ["There is no raffle right now!"])

    async def test_ForceEndCommand_WhenRaffleOpen_ShouldCancelTimerAndCloseRaffle(self):
        bot = FakeBot()
        command = FakeCommand()
        task = FakeTask()
        active_raffle = Raffle()
        active_raffle.open = True
        active_raffle.task = task
        active_raffle.close = AsyncMock()
        raffle_module.raffle = active_raffle
        commands = raffle_module.make_commands(bot)

        await commands["forceend"](command)

        self.assertTrue(task.cancelled)
        active_raffle.close.assert_awaited_once_with(command.reply, bot.pool)

    async def test_ForceEndCommand_WhenNoRaffleOpen_ShouldNotifyUser(self):
        bot = FakeBot()
        command = FakeCommand()
        commands = raffle_module.make_commands(bot)

        await commands["forceend"](command)

        self.assertEqual(command.replies, ["There is no raffle open right now!"])

    async def test_RedrawCommand_WhenRaffleExists_ShouldRedrawWithPool(self):
        bot = FakeBot()
        command = FakeCommand()
        active_raffle = Raffle()
        active_raffle.redraw = AsyncMock()
        raffle_module.raffle = active_raffle
        commands = raffle_module.make_commands(bot)

        await commands["redraw"](command)

        active_raffle.redraw.assert_awaited_once_with(command.reply, bot.pool)

    async def test_RedrawCommand_WhenNoRaffleExists_ShouldNotifyUser(self):
        bot = FakeBot()
        command = FakeCommand()
        commands = raffle_module.make_commands(bot)

        await commands["redraw"](command)

        self.assertEqual(command.replies, ["There is no raffle right now!"])

    async def test_ResolveCommand_WhenRaffleExists_ShouldResolveAndClearRaffle(self):
        bot = FakeBot()
        command = FakeCommand()
        active_raffle = Raffle()
        active_raffle.resolve = AsyncMock()
        raffle_module.raffle = active_raffle
        commands = raffle_module.make_commands(bot)

        await commands["resolve"](command)

        active_raffle.resolve.assert_awaited_once_with(command.reply)
        self.assertIsNone(raffle_module.raffle)
        self.assertEqual(command.replies, ["The current raffle has been resolved!"])

    async def test_ResolveCommand_WhenNoRaffleExists_ShouldNotifyUser(self):
        bot = FakeBot()
        command = FakeCommand()
        commands = raffle_module.make_commands(bot)

        await commands["resolve"](command)

        self.assertEqual(command.replies, ["There is no raffle right now!"])

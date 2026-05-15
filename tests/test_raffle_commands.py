import unittest
from unittest.mock import AsyncMock, patch

from tests.support.dependency_stubs import install_test_environment
from tests.support.fakes import FakeBot, FakeCommand


install_test_environment()

import raffle as raffle_module
from raffle import Raffle


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

    async def test_MyTicketsCommand_WhenTwitchUserUnresolved_ShouldNotReadDatabase(self):
        bot = FakeBot()
        command = FakeCommand(user_id=7, name="viewer")
        commands = raffle_module.make_commands(bot)

        with patch("raffle.get_twitch_user_id", new=AsyncMock(return_value=None)):
            await commands["mytickets"](command)

        self.assertEqual(command.replies, ["Could not resolve your Twitch account."])
        self.assertEqual(bot.db_calls, [])

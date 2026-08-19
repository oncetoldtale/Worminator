import asyncio
import unittest
from unittest.mock import AsyncMock, Mock, patch

import main as main_module
from main import Worminator
from tests.support.dependency_stubs import install_test_environment
from tests.support.fakes import (
    FakeChatClient,
    FakeCloseablePool,
    FakeReadyEvent,
    FakeTask,
    FakeTwitchClient,
    FakeUserAuthenticator,
)

install_test_environment()


async def successful_operation(value):
    return value * 2


async def failing_operation():
    raise RuntimeError("boom")


class WorminatorTests(unittest.IsolatedAsyncioTestCase):
    async def test_Start_WhenInputStopsBot_ShouldAuthenticateRegisterCommandsAndCleanup(self):
        bot = Worminator()
        twitch = FakeTwitchClient()
        chat = FakeChatClient()
        command_handler = Mock()
        authenticator = FakeUserAuthenticator(twitch, ["scope"])

        with (
            patch("main.Twitch", new=AsyncMock(return_value=twitch)) as twitch_factory,
            patch("main.UserAuthenticator", return_value=authenticator) as authenticator_factory,
            patch("main.Chat", new=AsyncMock(return_value=chat)) as chat_factory,
            patch("main.raffle.make_commands", return_value={"enter": command_handler}) as make_commands,
            patch("builtins.input", return_value=""),
        ):
            await bot.start()

        twitch_factory.assert_awaited_once()
        authenticator_factory.assert_called_once_with(twitch, main_module.USER_SCOPE)
        chat_factory.assert_awaited_once_with(twitch)
        make_commands.assert_called_once_with(bot)
        self.assertTrue(authenticator.authenticate_called)
        self.assertEqual(twitch.authentications, [("token", main_module.USER_SCOPE, "refresh-token")])
        self.assertEqual(chat.events, [(main_module.ChatEvent.READY, bot.on_ready)])
        self.assertEqual(chat.commands, {"enter": command_handler})
        self.assertTrue(chat.started)
        self.assertTrue(chat.stopped)
        self.assertTrue(twitch.closed)

    async def test_OnReady_WhenPoolAndWorkerMissing_ShouldJoinChannelCreatePoolAndStartWorker(self):
        bot = Worminator()
        ready_event = FakeReadyEvent()
        pool = FakeCloseablePool()
        task = FakeTask()

        def fake_create_task(coro):
            coro.close()
            return task

        with (
            patch("main.TARGET_CHANNEL", "test_channel"),
            patch("main.create_pool", new=AsyncMock(return_value=pool)) as create_pool,
            patch("main.asyncio.create_task", side_effect=fake_create_task) as create_task,
        ):
            await bot.on_ready(ready_event)

        self.assertEqual(ready_event.chat.joined_rooms, ["test_channel"])
        create_pool.assert_awaited_once()
        create_task.assert_called_once()
        self.assertIs(bot.pool, pool)
        self.assertIs(bot.db_worker_task, task)

    async def test_OnReady_WhenPoolAndWorkerExist_ShouldReuseExistingResources(self):
        bot = Worminator()
        ready_event = FakeReadyEvent()
        pool = FakeCloseablePool()
        task = FakeTask()
        bot.pool = pool
        bot.db_worker_task = task

        with (
            patch("main.TARGET_CHANNEL", "test_channel"),
            patch("main.create_pool", new=AsyncMock()) as create_pool,
            patch("main.asyncio.create_task") as create_task,
        ):
            await bot.on_ready(ready_event)

        self.assertEqual(ready_event.chat.joined_rooms, ["test_channel"])
        create_pool.assert_not_awaited()
        create_task.assert_not_called()
        self.assertIs(bot.pool, pool)
        self.assertIs(bot.db_worker_task, task)

    async def test_QueueDb_WhenOperationSucceeds_ShouldReturnOperationResult(self):
        bot = Worminator()
        bot.db_worker_task = asyncio.create_task(bot.db_worker())

        try:
            result = await bot.queue_db(successful_operation, 21)
        finally:
            await bot.stop()

        self.assertEqual(result, 42)
        self.assertIsNone(bot.db_worker_task)

    async def test_QueueDb_WhenOperationFails_ShouldPropagateException(self):
        bot = Worminator()
        bot.db_worker_task = asyncio.create_task(bot.db_worker())

        try:
            with self.assertRaisesRegex(RuntimeError, "boom"):
                await bot.queue_db(failing_operation)
        finally:
            await bot.stop()

    async def test_Stop_WhenWorkerAndPoolExist_ShouldStopWorkerAndClosePool(self):
        bot = Worminator()
        pool = FakeCloseablePool()
        bot.pool = pool
        bot.db_worker_task = asyncio.create_task(bot.db_worker())

        await bot.stop()

        self.assertTrue(pool.closed)
        self.assertIsNone(bot.pool)
        self.assertIsNone(bot.db_worker_task)

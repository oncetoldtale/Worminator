import asyncio
import unittest

from tests.support.dependency_stubs import install_test_environment
from tests.support.fakes import FakeCloseablePool


install_test_environment()

from main import Worminator


async def successful_operation(value):
    return value * 2


async def failing_operation():
    raise RuntimeError("boom")


class WorminatorTests(unittest.IsolatedAsyncioTestCase):
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

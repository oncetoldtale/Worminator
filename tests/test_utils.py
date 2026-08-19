import unittest

from tests.support.dependency_stubs import install_test_environment
from tests.support.fakes import FakeTwitch, FakeTwitchUser
from utils import get_twitch_user_id

install_test_environment()


class UtilsTests(unittest.IsolatedAsyncioTestCase):
    async def test_GetTwitchUserId_WhenUserExists_ShouldReturnIntegerUserId(self):
        twitch = FakeTwitch([FakeTwitchUser(123)])

        user_id = await get_twitch_user_id("alice", twitch)

        self.assertEqual(user_id, 123)
        self.assertEqual(twitch.requested_logins, [["alice"]])

    async def test_GetTwitchUserId_WhenUserMissing_ShouldReturnNone(self):
        twitch = FakeTwitch([])

        user_id = await get_twitch_user_id("missing_user", twitch)

        self.assertIsNone(user_id)
        self.assertEqual(twitch.requested_logins, [["missing_user"]])

from twitchAPI.chat import Chat, EventData, ChatMessage, ChatSub, ChatCommand
from twitchAPI.type import AuthScope, ChatEvent
from twitchAPI.oauth import UserAuthenticator
from twitchAPI.twitch import Twitch

import asyncio

async def get_twitch_user_id(username: str, twitch: Twitch) -> int | None:
    async for user in twitch.get_users(logins=[username]):
        return int(user.id)
    return None
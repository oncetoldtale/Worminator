from twitchAPI.twitch import Twitch


async def get_twitch_user_id(username: str, twitch: Twitch) -> int | None:
    async for user in twitch.get_users(logins=[username]):
        return int(user.id)
    return None

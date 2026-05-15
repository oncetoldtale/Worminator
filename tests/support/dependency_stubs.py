import os
import sys
import types


def install_dependency_stubs():
    twitch_package = types.ModuleType("twitchAPI")
    chat_module = types.ModuleType("twitchAPI.chat")
    type_module = types.ModuleType("twitchAPI.type")
    oauth_module = types.ModuleType("twitchAPI.oauth")
    twitch_module = types.ModuleType("twitchAPI.twitch")
    dotenv_module = types.ModuleType("dotenv")
    asyncpg_module = types.ModuleType("asyncpg")

    class Dummy:
        pass

    class AuthScope:
        CHAT_READ = object()
        CHAT_EDIT = object()
        CHANNEL_MANAGE_BROADCAST = object()

    class ChatEvent:
        READY = object()

    chat_module.Chat = Dummy
    chat_module.EventData = Dummy
    chat_module.ChatMessage = Dummy
    chat_module.ChatSub = Dummy
    chat_module.ChatCommand = Dummy
    type_module.AuthScope = AuthScope
    type_module.ChatEvent = ChatEvent
    oauth_module.UserAuthenticator = Dummy
    twitch_module.Twitch = Dummy
    dotenv_module.load_dotenv = lambda: None
    asyncpg_module.Pool = Dummy
    asyncpg_module.Connection = Dummy
    asyncpg_module.pool = Dummy

    sys.modules.setdefault("twitchAPI", twitch_package)
    sys.modules.setdefault("twitchAPI.chat", chat_module)
    sys.modules.setdefault("twitchAPI.type", type_module)
    sys.modules.setdefault("twitchAPI.oauth", oauth_module)
    sys.modules.setdefault("twitchAPI.twitch", twitch_module)
    sys.modules.setdefault("dotenv", dotenv_module)
    sys.modules.setdefault("asyncpg", asyncpg_module)


def install_test_environment():
    os.environ.setdefault("DB_PORT", "5432")
    os.environ.setdefault("TWITCHSUPERADMINID", "123")
    install_dependency_stubs()

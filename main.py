from twitchAPI.chat import Chat, EventData, ChatMessage, ChatSub, ChatCommand
from twitchAPI.type import AuthScope, ChatEvent
from twitchAPI.oauth import UserAuthenticator
from twitchAPI.twitch import Twitch
import asyncio

import time
import obsws_python as obs
from dotenv import load_dotenv
import os

import raffle
import postgres
from postgres import create_pool

load_dotenv()

APP_ID = os.getenv("TWITCH_APPID")
APP_SECRET = os.getenv("TWITCH_APPSECRET")
TARGET_CHANNEL = os.getenv("TARGET_CHANNEL")

obs_ip = os.getenv("OBS_IP")
obs_port = os.getenv("OBS_PORT")
obs_password = os.getenv("OBS_PASSWORD")

USER_SCOPE = [AuthScope.CHAT_READ,
              AuthScope.CHAT_EDIT,
              AuthScope.CHANNEL_MANAGE_BROADCAST]

class Worminator:
    def __init__(self):
        self.twitch = None
        self.discord = None
        self.pool = None
        self.chat = None
        self.raffle = None
        self.winners = []

        self.db_queue = asyncio.Queue()
        self.db_worker_task = None

    async def db_worker(self):
        print("[DB WORKER] Started.")
        while True:
            func, args, future = await self.db_queue.get()
            try:
                print(f"[DB WORKER] Running {func.__name__}")
                result = await func(*args)
                future.set_result(result)
            except Exception as e:
                print(f"[DB WORKER ERROR] {func.__name__}: {e}")
                future.set_exception(e)
            finally:
                self.db_queue.task_done()

    async def queue_db(self, func, *args):
        future = asyncio.get_event_loop().create_future()
        await self.db_queue.put((func, args, future))
        return await future

    async def on_ready(self, ready_event: EventData):
        await ready_event.chat.join_room(TARGET_CHANNEL)

        if not self.pool:
            self.pool = await create_pool()

        if not self.db_worker_task:
            self.db_worker_task = asyncio.create_task(self.db_worker())

        print(f"Bot has joined {TARGET_CHANNEL} channel.")
    
    async def start(self):
        self.twitch = await Twitch(APP_ID, APP_SECRET)
        auth = UserAuthenticator(self.twitch, USER_SCOPE)
        token, refresh_token = await auth.authenticate()
        await self.twitch.set_user_authentication(token, USER_SCOPE, refresh_token)

        self.chat = await Chat(self.twitch)
        self.chat.register_event(ChatEvent.READY, self.on_ready)

        raffle_commands = raffle.make_commands(self)
        for name, handler in raffle_commands.items():
            self.chat.register_command(name, handler)

        self.chat.start()

        try:
            input("Worminator is online. Press ENTER to stop...\n")
        finally:
            self.chat.stop()
            await self.twitch.close()


def main():
    bot = Worminator()
    asyncio.run(bot.start())

main()
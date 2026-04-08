from twitchAPI.chat import Chat, EventData, ChatMessage, ChatSub, ChatCommand
from twitchAPI.type import AuthScope, ChatEvent
from twitchAPI.oauth import UserAuthenticator
from twitchAPI.twitch import Twitch

import asyncio
import csv
import random
import os
from dotenv import load_dotenv
from typing import TYPE_CHECKING

from utils import get_twitch_user_id

import asyncpg

import postgres

load_dotenv()
SUPERADMIN_ID = int(os.getenv("TWITCHSUPERADMINID", "0"))

class Raffle:
    def __init__(self, duration=180, ticket_amt=1):
        self.duration = int(duration)
        self.ticket_amt = ticket_amt
        self.open = False
        self.users = {
            "Entries" : {}, #user_id: username
            "Claims" : {}, #user_id: username 
            "Redrawn" : {}, #user_id: username
        }
        self.tickets = {}
        self.task = None
        self.send_message = None
        self.current_winner = None
        self.bot = None
        self.redrawn = []

    async def _run_timer(self, send_message):
        for remaining in range(self.duration, 0, -1):
            print(f"\rRaffle closing in: {remaining}s  ", end="", flush=True)
            await asyncio.sleep(1)
        print("\rRaffle timer ended!              ")
        await self.close(send_message)

    async def start(self, send_message, pool: asyncpg.Pool):
        self.pool = pool
        self.send_message = send_message

        if self.open:
            print("[Raffle] Attempted to start a raffle but one is already running.")
            await send_message("Raffle already running!")
            return
        self.open = True
        await self.load_tickets(pool)
        print(f"[Raffle] Raffle started. Duration: {self.duration}s | Ticket award: {self.ticket_amt}")
        await send_message(f"New Coaching raffle has been opened for {self.duration} seconds. !enter in Twitch Chat to enter. !claim to claim a ticket.")
        self.task = asyncio.create_task(self._run_timer(send_message))

    async def close(self, send_message):
        if not self.open:
            return
        self.open = False

        if not self.users["Entries"]:
            print("[Raffle] Raffle closed with no entries.")
            await send_message("No entries. Raffle closed.")
            return

        winner_id, winner_name = self.draw()
        self.current_winner = (winner_id, winner_name)
        print(f"[Raffle] Winner drawn: {winner_name} (ID: {winner_id})")
        await send_message(f"Congratulations {winner_name}, you have been selected for coaching! Use !resolve to confirm or !redraw to pick again.")

    async def enter(self, user_id: int, username: str, send_message):
        if not self.open:
            await send_message(f"{username}, no raffle is open!")
            return

        if user_id in self.users["Entries"]:
            print(f"[Raffle] {username} tried to enter but is already in the raffle.")
            await send_message(f"{username}, you have already entered the raffle!")
            return
    
        if user_id in self.bot.winners:
            print(f"[Raffle] {username} tried to enter but has already won a raffle this session.")
            await send_message(f"{username}, you have already WON a raffle this session, please !claim instead!")
            return

        if user_id in self.users["Claims"]:
            del self.users["Claims"][user_id]
            self.users["Entries"][user_id] = username
            print(f"[Raffle] {username} moved from Claims to Entries.")
            await send_message(f"{username}, you have been moved into the raffle!")
            return

        self.users["Entries"][user_id] = username
        print(f"[Raffle] {username} entered the raffle. Total entries: {len(self.users['Entries'])}")
        await send_message(f"{username}, you have entered the raffle!")
                
    async def claim(self, user_id: int, username: str, send_message):
        if user_id in self.users["Claims"]:
            print(f"[Raffle] {username} tried to claim but already has a ticket.")
            await send_message(f"{username}, you have already claimed your ticket!")
            return

        if user_id in self.users["Entries"]:
            del self.users["Entries"][user_id]
            self.users["Claims"][user_id] = username
            print(f"[Raffle] {username} moved from Entries to Claims.")
            await send_message(f"{username}, you have claimed your ticket and have been removed from the raffle!")
            return

        self.users["Claims"][user_id] = username
        print(f"[Raffle] {username} claimed a ticket. Total claimers: {len(self.users['Claims'])}")
        await send_message(f"{username}, you have claimed a ticket!")

    def draw(self) -> tuple[int, str]:
        raffle_pool = []

        for user_id, username in self.users["Entries"].items():
            ticket_count = self.tickets.get(user_id, 1)
            raffle_pool.extend([(user_id, username)] * ticket_count)

        return random.choice(raffle_pool)
    
    async def redraw(self, send_message):
        if not self.current_winner:
            print("[Raffle] Redraw attempted but there is no current winner.")
            await send_message("No active winner to redraw.")
            return

        prev_winner_id, prev_winner_name = self.current_winner
        self.users["Redrawn"][prev_winner_id] = prev_winner_name
        del self.users["Entries"][prev_winner_id]

        winner_id, winner_name = self.draw()
        self.current_winner = (winner_id, winner_name)
        print(f"[Raffle] Redrawn. New winner: {winner_name} (ID: {winner_id})")
        await send_message(f"Redrawn! New winner is {winner_name}. Use !resolve to confirm or !redraw to pick again.")

    def cancel(self):
        self.open = False
        if self.task:
            self.task.cancel()
        print("[Raffle] Raffle has been cancelled.")
        
    def extend(self, additional_seconds=60):
        if self.task:
            self.task.cancel()
        self.duration = additional_seconds
        print(f"[Raffle] Raffle extended. New duration: {additional_seconds}s")
        self.task = asyncio.create_task(self._run_timer(self.send_message))

    async def load_tickets(self, pool: asyncpg.Pool):
        self.tickets = await postgres.get_all_tickets(pool) or {}
        print(f"[Raffle] Loaded tickets for {len(self.tickets)} users from database.")
 
    async def resolve(self, send_message):
        if not self.current_winner:
            print("[Raffle] Resolve attempted but there is no current winner.")
            await send_message("No active winner to resolve.")
            return

        winner_id, winner_name = self.current_winner

        losers = [
            (uid, uname)
            for uid, uname in self.users["Entries"].items()
            if uid != winner_id
        ]

        redrawn = [
            (uid, uname)
            for uid, uname in self.users["Redrawn"].items()
       ]

        claimers = [
            (uid, uname)
            for uid, uname in self.users["Claims"].items()
        ]
        print(f"losers list: {losers}")
        print(f"redrawn list: {redrawn}")
        print(f"claimers list: {claimers}")

        await self.bot.queue_db(
            postgres.set_user_tickets_zero,
            self.pool,
            [(winner_id, winner_name)]
        )

        await self.bot.queue_db(
            postgres.update_user_tickets,
            self.pool,
            losers + claimers + redrawn,
            self.ticket_amt
        )
        
        self.bot.winners.append(winner_id)
        print(f"[Raffle] Resolved. Winner: {winner_name} | Losers awarded tickets: {len(losers)} | Claimers awarded tickets: {len(claimers)}")

raffle: Raffle | None = None


def user_is_superadmin(cmd: ChatCommand) -> bool:
    return int(cmd.user.id) == SUPERADMIN_ID

def make_commands(bot):

    async def new_raffle_command(cmd: ChatCommand):
        global raffle
        if not user_is_superadmin(cmd):
            return

        duration = cmd.parameter.strip()
        if not duration or not duration.isdigit():
            print(f"[Command] !newraffle called by {cmd.user.name} with invalid duration: '{cmd.parameter}'")
            await cmd.reply("Please input a valid duration (int).")
            return

        print(f"[Command] !newraffle called by {cmd.user.name}. Duration: {duration}s")
        raffle = Raffle(int(duration))
        raffle.bot = bot
        await raffle.start(cmd.reply, bot.pool)

    async def extend_command(cmd: ChatCommand):
        if not raffle or not raffle.open:
            await cmd.reply("There is no raffle open right now!")
            return
        if not user_is_superadmin(cmd):
            return

        seconds = cmd.parameter.strip()
        if not seconds or not seconds.isdigit():
            print(f"[Command] !extend called by {cmd.user.name} with invalid input: '{cmd.parameter}'")
            await cmd.reply("Please input a valid duration (int).")
            return

        print(f"[Command] !extend called by {cmd.user.name}. Extending by {seconds}s")
        raffle.extend(int(seconds))
        await cmd.reply(f"Raffle extended by {seconds} seconds!")

    async def clear_command(cmd: ChatCommand):
        if not user_is_superadmin(cmd):
            return
        if not raffle:
            await cmd.reply("There is no raffle right now!")
            return
        raffle.users["Entries"].clear()
        raffle.users["Claims"].clear()
        print(f"[Command] !clear called by {cmd.user.name}. All entries and claims cleared.")
        await cmd.reply("Raffle entries and claims have been cleared.")

    async def cancel_command(cmd: ChatCommand):
        global raffle
        if not user_is_superadmin(cmd):
            return
        if not raffle:
            await cmd.reply("There is no raffle right now!")
            return
        print(f"[Command] !cancel called by {cmd.user.name}.")
        raffle.cancel()
        raffle = None
        await cmd.reply("Raffle has been cancelled.")

    async def force_end_command(cmd: ChatCommand):
        if not user_is_superadmin(cmd):
            return
        if not raffle or not raffle.open:
            await cmd.reply("There is no raffle open right now!")
            return
        print(f"[Command] !forceend called by {cmd.user.name}. Force ending raffle and drawing winner.")
        raffle.task.cancel()
        await raffle.close(cmd.reply)

    async def redraw_command(cmd: ChatCommand):
        if not raffle:
            await cmd.reply("There is no raffle right now!")
            return
        if not user_is_superadmin(cmd):
            return
        print(f"[Command] !redraw called by {cmd.user.name}.")
        await raffle.redraw(cmd.reply)

    async def resolve_command(cmd: ChatCommand):
        global raffle
        if not raffle:
            await cmd.reply("There is no raffle right now!")
            return
        if not user_is_superadmin(cmd):
            return
        print(f"[Command] !resolve called by {cmd.user.name}.")
        await raffle.resolve(cmd.reply)
        await cmd.reply("The current raffle has been resolved!")
        raffle = None
        
    async def enter_command(cmd: ChatCommand):
        if not raffle or not raffle.open:
            await cmd.reply("There is no raffle open right now!")
            return
        print(f"{int(cmd.user.id)}, {cmd.user.name}")
        await raffle.enter(int(cmd.user.id), cmd.user.name, cmd.reply)

    async def claim_command(cmd: ChatCommand):
        if not raffle or not raffle.open:
            await cmd.reply("There is no raffle open right now!")
            return
        await raffle.claim(int(cmd.user.id), cmd.user.name, cmd.reply)

    async def add_ticket_command(cmd: ChatCommand):
        if not user_is_superadmin(cmd):
            return
        print(f"[Command] !addticket called by {cmd.user.name}.")

        parts = cmd.parameter.strip().split()
        if len(parts) != 2 or not parts[1].isdigit():
            await cmd.reply("Usage: !addticket USERNAME ticket_amt")
            return

        username, credit_amount = parts[0], int(parts[1])

        twitch_id = await get_twitch_user_id(username, bot.twitch)
        if twitch_id is None:
            await cmd.reply(f"Could not find Twitch user: {username}")
            return

        await bot.queue_db(
            postgres.update_user_tickets,
            bot.pool,
            [(twitch_id, username)],
            credit_amount
        )

        print(f"[Command] !addticket called by {cmd.user.name}. Crediting {credit_amount} tickets to {username}.")
        await cmd.reply(f"Added {credit_amount} ticket(s) to {username}!")

    async def drop_tables_command(cmd: ChatCommand):
        if not user_is_superadmin(cmd):
            print(f"[CMD] Unauthorized drop_tables attempt by user '{cmd.user.name}' (id={cmd.user.id}).")
            return
        print(f"[CMD] drop_tables called by superadmin '{cmd.user.name}'.")
        await bot.queue_db(
            postgres.debug_drop_all_tables,
            bot.pool,
        )
        await cmd.reply("All tables dropped.")
        print(f"[CMD] drop_tables completed and reply sent.")

    async def new_tables_command(cmd: ChatCommand):
        if not user_is_superadmin(cmd):
            print(f"[CMD] Unauthorized new_tables attempt by user '{cmd.user.name}' (id={cmd.user.id}).")
            return
        print(f"[CMD] new_tables called by superadmin '{cmd.user.name}'.")
        await bot.queue_db(
            postgres.debug_create_new_tables,
            bot.pool,
        )
        await cmd.reply("Tables created.")
        print(f"[CMD] new_tables completed and reply sent.")

    async def my_ticket_command(cmd: ChatCommand):
        twitch_id = await get_twitch_user_id(cmd.user.name, bot.twitch)
        if twitch_id is None:
            await cmd.reply("Could not resolve your Twitch account.")
            return

        ticket_amt = await bot.queue_db(
            postgres.get_user_tickets,
            bot.pool,
            twitch_id
        )
        await cmd.reply(f"{cmd.user.name}, you have {ticket_amt} ticket(s).")

    return {
        "newraffle": new_raffle_command,
        "extend": extend_command,
        "clear": clear_command,
        "forceend": force_end_command,
        "cancel": cancel_command,
        "redraw": redraw_command,
        "resolve": resolve_command,
        "enter": enter_command,
        "claim": claim_command,
        "addticket": add_ticket_command,
        "mytickets": my_ticket_command,
        "debugdroptables": drop_tables_command,
        "debugnewtables": new_tables_command,
    }

# ONCE RAFFLE IS LIVE, OBS SCENE UPDATED W/ TIMER. ALSO RUN ADS DURING THIS TIME.
# A NEW STUDENT HAS ARRIVED! - MOTION GRAPHIC OVERLAY!
# Fetch UserID

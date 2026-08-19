import os

import asyncpg
from dotenv import load_dotenv

load_dotenv()

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_DATABASE = os.getenv("DB_DATABASE")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT"))

SUPERADMIN_ID = os.getenv("TWITCHSUPERADMINID")


async def create_pool() -> asyncpg.Pool:
    print(f"[DB] Creating connection pool (host={DB_HOST}, db={DB_DATABASE}, user={DB_USER})...")
    connection_pool = await asyncpg.create_pool(
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_DATABASE,
        host=DB_HOST,
        port=DB_PORT,
        min_size=1,
        max_size=10,
        command_timeout=10,
        timeout=10,
    )
    print("[DB] Connection pool created successfully.")
    return connection_pool


def get_conn(func):
    async def wrapper(pool: asyncpg.Pool, *args, **kwargs):
        try:
            result = None
            print(f"[DB] Acquiring connection for '{func.__name__}'...")
            async with pool.acquire() as conn:
                result = await func(conn, *args, **kwargs)
            print(f"[DB] '{func.__name__}' completed successfully.")
            return result
        except Exception as error:
            print(f"[DB] Error in '{func.__name__}': {error}")
            raise

    return wrapper


@get_conn
async def get_all_tickets(conn: asyncpg.Connection) -> dict:
    print("[DB] Fetching all user ticket counts...")
    rows = await conn.fetch("SELECT user_id, ticket_count FROM users")
    print(f"[DB] Retrieved ticket counts for {len(rows)} user(s).")
    return {row["user_id"]: row["ticket_count"] for row in rows}


@get_conn
async def get_user_tickets(conn: asyncpg.Connection, user_id: int) -> int:
    print(f"[DB] Fetching ticket count for user {user_id}...")
    row = await conn.fetchrow("SELECT ticket_count FROM users WHERE user_id = $1", user_id)
    print(f"[DB] Retrieved ticket count: {row['ticket_count'] if row else 'user not found'}.")
    return row["ticket_count"] if row else 0


@get_conn
async def update_user_tickets(conn: asyncpg.Connection, users: list[tuple[int, str]], ticket_amt: int) -> None:
    print(f"[DB] Updating tickets for {len(users)} user(s) by +{ticket_amt}...")
    insert_values = [(twitch_id, username, ticket_amt) for twitch_id, username in users]
    await conn.executemany(
        """
        INSERT INTO users (user_id, username, ticket_count)
        VALUES ($1, $2, $3)
        ON CONFLICT (user_id)
        DO UPDATE SET
            ticket_count = users.ticket_count + EXCLUDED.ticket_count,
            username = EXCLUDED.username
    """,
        insert_values,
    )
    print(f"[DB] Ticket update complete for {len(users)} user(s).")


@get_conn
async def set_user_tickets_zero(conn: asyncpg.Connection, users: list[tuple[str, str]]) -> None:
    print(f"[DB] Zeroing tickets for {len(users)} user(s)...")
    insert_values = [(twitch_id, username) for twitch_id, username in users]
    await conn.executemany(
        """
        UPDATE users
        SET ticket_count = 0,
            username = $2
        WHERE user_id = $1
    """,
        insert_values,
    )
    print(f"[DB] Ticket reset complete for {len(users)} user(s).")


@get_conn
async def resolve_raffle_tickets(
    conn: asyncpg.Connection, winner: tuple[int, str] | None, users_to_credit: list[tuple[int, str]], ticket_amt: int
) -> None:
    winner_id, winner_name = winner if winner else (None, None)
    print(f"[DB] Resolving raffle tickets atomically. Winner: {winner_name} ({winner_id}) ")

    async with conn.transaction():
        if winner:
            await conn.execute(
                """
                INSERT INTO users (user_id, username, ticket_count, times_coached)
                VALUES ($1, $2, 0, 1)
                ON CONFLICT (user_id)
                DO UPDATE SET
                    ticket_count = 0,
                    username = EXCLUDED.username,
                    times_coached = users.times_coached + 1
                """,
                winner_id,
                winner_name,
            )

        if users_to_credit:
            insert_values = [(twitch_id, username, ticket_amt) for twitch_id, username in users_to_credit]
            await conn.executemany(
                """
                INSERT INTO users (user_id, username, ticket_count)
                VALUES ($1, $2, $3)
                ON CONFLICT (user_id)
                DO UPDATE SET
                    ticket_count = users.ticket_count + EXCLUDED.ticket_count,
                    username = EXCLUDED.username
                """,
                insert_values,
            )

    print("[DB] Atomic raffle ticket resolution complete.")

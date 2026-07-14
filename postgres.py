import asyncio
import os
from datetime import datetime, timezone

import asyncpg
from dotenv import load_dotenv

load_dotenv()

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_DATABASE = os.getenv("DB_DATABASE")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT"))

SUPERADMIN_ID = int(os.getenv("TWITCHSUPERADMINID"))

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
    print(f"[DB] Connection pool created successfully.")
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


async def _get_or_create_user(conn: asyncpg.Connection, twitch_id: int, username: str) -> int:
    """Resolve a twitch_id to the internal user_id, creating the user if needed."""
    row = await conn.fetchrow(
        """
        INSERT INTO users (twitch_id, username)
        VALUES ($1, $2)
        ON CONFLICT (twitch_id) DO UPDATE SET username = EXCLUDED.username
        RETURNING user_id
        """,
        twitch_id, username,
    )
    return row["user_id"]


@get_conn
async def get_all_tickets(conn: asyncpg.Connection) -> dict:
    print(f"[DB] Fetching all user ticket counts...")
    rows = await conn.fetch(
        """
        SELECT u.twitch_id AS user_id, COALESCE(SUM(te.amount), 0) AS ticket_count
        FROM users u
        LEFT JOIN ticket_events te ON te.user_id = u.user_id
        WHERE u.twitch_id IS NOT NULL
        GROUP BY u.twitch_id
        """
    )
    print(f"[DB] Retrieved ticket counts for {len(rows)} user(s).")
    return {row["user_id"]: row["ticket_count"] for row in rows}

@get_conn
async def get_user_tickets(conn: asyncpg.Connection, user_id: int) -> int:
    print(f"[DB] Fetching ticket count for user {user_id}...")
    row = await conn.fetchrow(
        """
        SELECT COALESCE(SUM(te.amount), 0) AS ticket_count
        FROM users u
        LEFT JOIN ticket_events te ON te.user_id = u.user_id
        WHERE u.twitch_id = $1
        """,
        user_id,
    )
    ticket_count = row["ticket_count"] if row else 0
    print(f"[DB] Retrieved ticket count: {ticket_count}.")
    return ticket_count

@get_conn
async def update_user_tickets(
    conn: asyncpg.Connection,
    users: list[tuple[int, str]],
    ticket_amt: int,
    issued_by: int = SUPERADMIN_ID,
) -> None:
    print(f"[DB] Updating tickets for {len(users)} user(s) by +{ticket_amt}...")

    async with conn.transaction():
        issuer_id = await _get_or_create_user(conn, issued_by, "SuperAdmin")

        if users:
            twitch_ids = [twitch_id for twitch_id, _ in users]
            usernames = [username for _, username in users]
            await conn.execute(
                """
                WITH input_users AS (
                    SELECT * FROM unnest($1::bigint[], $2::text[]) AS t(twitch_id, username)
                ),
                upserted AS (
                    INSERT INTO users (twitch_id, username)
                    SELECT twitch_id, username FROM input_users
                    ON CONFLICT (twitch_id) DO UPDATE SET username = EXCLUDED.username
                    RETURNING user_id
                )
                INSERT INTO ticket_events (user_id, event_type, amount, issued_by)
                SELECT user_id, 'issued', $3, $4 FROM upserted
                """,
                twitch_ids, usernames, ticket_amt, issuer_id,
            )

    print(f"[DB] Ticket update complete for {len(users)} user(s).")

@get_conn
async def set_user_tickets_zero(
    conn: asyncpg.Connection,
    users: list[tuple[int, str]],
    issued_by: int = SUPERADMIN_ID,
) -> None:
    print(f"[DB] Zeroing tickets for {len(users)} user(s)...")

    async with conn.transaction():
        issuer_id = await _get_or_create_user(conn, issued_by, "SuperAdmin")

        for twitch_id, username in users:
            user_id = await _get_or_create_user(conn, twitch_id, username)

            balance_row = await conn.fetchrow(
                "SELECT COALESCE(SUM(amount), 0) AS balance FROM ticket_events WHERE user_id = $1",
                user_id,
            )
            balance = balance_row["balance"]

            if balance != 0:
                await conn.execute(
                    """
                    INSERT INTO ticket_events (user_id, event_type, amount, issued_by)
                    VALUES ($1, 'redeem', $2, $3)
                    """,
                    user_id, -balance, issuer_id,
                )

    print(f"[DB] Ticket reset complete for {len(users)} user(s).")

@get_conn
async def resolve_raffle_tickets(
    conn: asyncpg.Connection,
    raffle_id: int,
    winner: tuple[int, str] | None,
    users_to_credit: list[tuple[int, str]],
    session_datetime: datetime | None = None,
    issued_by: int = SUPERADMIN_ID,
) -> None:
    winner_id, winner_name = winner if winner else (None, None)
    print(f"[DB] Resolving raffle tickets atomically. Winner: {winner_name} ({winner_id}) ")

    async with conn.transaction():
        issuer_id = await _get_or_create_user(conn, issued_by, "SuperAdmin")

        if winner:
            winner_user_id = await _get_or_create_user(conn, winner_id, winner_name)

            balance_row = await conn.fetchrow(
                "SELECT COALESCE(SUM(amount), 0) AS balance FROM ticket_events WHERE user_id = $1",
                winner_user_id,
            )
            balance = balance_row["balance"]

            if balance != 0:
                await conn.execute(
                    """
                    INSERT INTO ticket_events (user_id, event_type, amount, raffle_id, issued_by)
                    VALUES ($1, 'raffle_win', $2, $3, $4)
                    """,
                    winner_user_id, -balance, raffle_id, issuer_id,
                )

            await conn.execute(
                """
                INSERT INTO coaching_sessions (user_id, session_datetime)
                VALUES ($1, $2)
                """,
                winner_user_id, session_datetime or datetime.now(timezone.utc),
            )

            await conn.execute(
                """
                UPDATE raffles
                SET status = 'resolved', winner_id = $1, ends_at = now()
                WHERE raffle_id = $2
                """,
                winner_user_id, raffle_id,
            )
        else:
            await conn.execute(
                "UPDATE raffles SET status = 'no winner', ends_at = now() WHERE raffle_id = $1",
                raffle_id,
            )

        if users_to_credit:
            twitch_ids = [twitch_id for twitch_id, _ in users_to_credit]
            usernames = [username for _, username in users_to_credit]
            await conn.execute(
                """
                WITH input_users AS (
                    SELECT * FROM unnest($1::bigint[], $2::text[]) AS t(twitch_id, username)
                ),
                upserted AS (
                    INSERT INTO users (twitch_id, username)
                    SELECT twitch_id, username FROM input_users
                    ON CONFLICT (twitch_id) DO UPDATE SET username = EXCLUDED.username
                    RETURNING user_id
                )
                INSERT INTO ticket_events (user_id, event_type, amount, raffle_id, issued_by)
                SELECT user_id, 'raffle_loss', $3, $4, $5 FROM upserted
                """,
                twitch_ids, usernames, raffle_id, issuer_id,
            )

    print("[DB] Atomic raffle ticket resolution complete.")

@get_conn
async def create_raffle(conn: asyncpg.Connection, duration_seconds: int) -> int:
    print(f"[DB] Creating new raffle (duration={duration_seconds}s)...")
    row = await conn.fetchrow(
        """
        INSERT INTO raffles (status, duration_seconds, starts_at)
        VALUES ('open', $1, now())
        RETURNING raffle_id
        """,
        duration_seconds,
    )
    print(f"[DB] Raffle created with raffle_id={row['raffle_id']}.")
    return row["raffle_id"]

@get_conn
async def update_raffle_status(conn: asyncpg.Connection, raffle_id: int, status: str) -> None:
    print(f"[DB] Updating raffle {raffle_id} status to '{status}'...")
    is_terminal = status in ("resolved", "cancelled", "no winner")
    await conn.execute(
        """
        UPDATE raffles
        SET status = $1,
            ends_at = CASE WHEN $3 THEN now() ELSE ends_at END
        WHERE raffle_id = $2
        """,
        status, raffle_id, is_terminal,
    )
    print(f"[DB] Raffle {raffle_id} status updated.")
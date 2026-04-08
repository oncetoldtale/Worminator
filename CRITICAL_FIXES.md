# Critical Fixes

## 1) Normalize Superadmin ID Comparisons
Issue:
`TWITCHSUPERADMINID` was loaded as a string while command user IDs were handled numerically in multiple places.

Impact:
Superadmin checks could fail unexpectedly due to type mismatch, allowing admin commands to be blocked even for the correct user.

Resolution:
`SUPERADMIN_ID` is now cast to `int` at load time, and all superadmin command checks use a single helper: `user_is_superadmin(cmd)`.

## 2) Guard Unresolved Twitch Users in Ticket Commands
Issue:
Ticket-related commands assumed `get_twitch_user_id(...)` always returned a valid ID.

Impact:
`!addticket` and `!mytickets` could pass `None` into DB operations, causing failures or inconsistent behavior.

Resolution:
Both commands now explicitly handle unresolved users:
- `!addticket` replies with `Could not find Twitch user: {username}` and exits.
- `!mytickets` replies with `Could not resolve your Twitch account.` and exits.

## 3) Re-raise Database Exceptions in Connection Wrapper
Issue:
The `get_conn` decorator logged DB exceptions but swallowed them.

Impact:
Callers could not detect failures reliably, reducing observability and masking real runtime errors.

Resolution:
After logging in the decorator, exceptions are now re-raised so upstream code can fail fast and handle errors properly.

## 4) Graceful DB Worker Shutdown and Pool Close
Issue:
The DB worker loop had no explicit stop signal, and DB pool shutdown was not coordinated with worker lifecycle.

Impact:
Shutdown could leave background tasks hanging or DB resources open longer than intended.

Resolution:
A dedicated stop signal was added for the worker queue. The worker now exits cleanly on that signal. A new async `stop()` method:
- enqueues the stop signal,
- awaits worker termination,
- closes the DB pool,
- sets `pool` to `None`.

Bot shutdown now calls `await self.stop()` after `self.chat.stop()`.

## 5) Atomic Raffle Resolve Ticket Updates
Issue:
Raffle resolution previously used separate DB operations for winner reset and ticket credits.

Impact:
Partial updates could occur if one operation succeeded and the next failed, causing ticket inconsistency.

Resolution:
A new DB method, `resolve_raffle_tickets(conn, winner, users_to_credit, ticket_amt)`, performs winner reset and loser/claimer credit updates in one transaction. The raffle resolve flow now calls this single atomic DB operation.

## Deferred Fix / Open Decision
Issue:
Destructive debug chat commands that can drop and recreate tables are exposed through chat command handlers.

Risk:
Even with superadmin checks, runtime-exposed destructive commands increase blast radius from credential leakage, account takeover, accidental invocation, and operational mistakes.

Recommended change:
Remove these commands from chat entirely, or strongly protect them behind additional controls (for example, environment-gated disable-by-default plus out-of-band confirmation).

Status in this PR:
This item is intentionally not implemented in code in this PR and is left for author decision.

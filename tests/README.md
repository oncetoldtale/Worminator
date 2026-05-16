# Worminator Tests

Python 3.10+ is required because the application uses modern type hint syntax.

## Running Tests On Windows

Use the PowerShell runner from the project root:

```powershell
.\tests\test.ps1 smoke
.\tests\test.ps1 regression
.\tests\test.ps1 all
```

The runner uses the Windows Python launcher by default:

```powershell
py -3
```

Override it if needed:

```powershell
.\tests\test.ps1 all -Python "python"
.\tests\test.ps1 all -Python "python3.13"
```

## Test Sets

### Smoke Tests

```powershell
.\tests\test.ps1 smoke
```

Runs the most important functional raffle flows from `tests/test_raffle_functional.py`.

Use this when you need a fast check that the main raffle behavior still works: users enter or claim, the raffle closes, a winner is selected, and tickets are awarded.

### Regression Tests

```powershell
.\tests\test.ps1 regression
```

Runs tests focused on previous bug fixes and critical support behavior:

- `tests/test_raffle_commands.py` - command validation, admin guards, unresolved users, command wrappers.
- `tests/test_postgres.py` - ticket persistence, DB wrapper behavior, atomic raffle resolution.
- `tests/test_main.py` - bot startup, ready event setup, DB worker lifecycle.
- `tests/test_utils.py` - Twitch user lookup behavior.

Use this after changing command handling, DB code, bot startup, or any area that previously had bugs.

### Full Test Suite

```powershell
.\tests\test.ps1 all
```

Runs every test under `tests/`.

Use this before committing, pushing, or opening a PR.

## Direct Commands

Use these commands if you do not want to run the PowerShell helper:

```powershell
py -3 -m unittest tests/test_raffle_functional.py
py -3 -m unittest tests/test_raffle_commands.py tests/test_postgres.py tests/test_main.py tests/test_utils.py
py -3 -m unittest discover -s tests
```

## Developer Guidance

Add or update tests whenever you add a feature, change business logic, or fix a bug.

- New user-facing raffle behavior should usually include a functional or business-rule test.
- Bug fixes should include a regression test that fails without the fix.
- DB changes should include tests for the expected SQL operation or transaction behavior.
- Keep reusable fakes and helpers in `tests/support/`; keep test files focused on scenarios and assertions.

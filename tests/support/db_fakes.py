class FakeAcquireContext:
    def __init__(self, connection, enter_error=None):
        self.connection = connection
        self.enter_error = enter_error

    async def __aenter__(self):
        if self.enter_error:
            raise self.enter_error
        return self.connection

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class FakePool:
    def __init__(self, connection, enter_error=None):
        self.connection = connection
        self.enter_error = enter_error

    def acquire(self):
        return FakeAcquireContext(self.connection, self.enter_error)


class FakeTransaction:
    def __init__(self):
        self.entered = False
        self.exited = False

    async def __aenter__(self):
        self.entered = True
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        self.exited = True
        return False


class FakeConnection:
    def __init__(self):
        self.fetch_rows = []
        self.fetchrow_result = None
        self.operations = []
        self.executemany_calls = []
        self.transaction_context = FakeTransaction()

    async def fetch(self, query):
        self.operations.append(("fetch", query))
        return self.fetch_rows

    async def fetchrow(self, query, *args):
        self.operations.append(("fetchrow", query, args))
        return self.fetchrow_result

    async def execute(self, query, *args):
        self.operations.append(("execute", query, args))

    async def executemany(self, query, values):
        self.executemany_calls.append((query, values))

    def transaction(self):
        return self.transaction_context

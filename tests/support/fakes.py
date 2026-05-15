class FakeBot:
    def __init__(self):
        self.pool = object()
        self.twitch = object()
        self.winners = []
        self.db_calls = []

    async def queue_db(self, func, *args):
        self.db_calls.append((func, args))
        return None


class FakeUser:
    def __init__(self, user_id=123, name="admin"):
        self.id = str(user_id)
        self.name = name


class FakeCommand:
    def __init__(self, user_id=123, name="admin", parameter=""):
        self.user = FakeUser(user_id, name)
        self.parameter = parameter
        self.replies = []

    async def reply(self, message):
        self.replies.append(message)


class FakeCloseablePool:
    def __init__(self):
        self.closed = False

    async def close(self):
        self.closed = True


class MessageRecorder:
    def __init__(self):
        self.messages = []

    async def __call__(self, message):
        self.messages.append(message)


class FakeTwitchUser:
    def __init__(self, user_id):
        self.id = str(user_id)


class FakeTwitchUsers:
    def __init__(self, users):
        self.users = users
        self.index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.index >= len(self.users):
            raise StopAsyncIteration
        user = self.users[self.index]
        self.index += 1
        return user


class FakeTwitch:
    def __init__(self, users):
        self.users = users
        self.requested_logins = []

    def get_users(self, logins):
        self.requested_logins.append(logins)
        return FakeTwitchUsers(self.users)

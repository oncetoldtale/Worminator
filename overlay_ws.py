import asyncio
import json
import os

from aiohttp import web

WEBSOCKET_DISABLED = os.getenv("WORMINATOR_WS_DISABLED", "").strip().lower() == "true"


class OverlayBroadcaster:
    def __init__(self, host="127.0.0.1", port=8765):
        self.host = host
        self.port = port
        self.clients = set()
        self.app = web.Application()

        self.app.add_routes([web.get("/ws", self.handle_ws)])
        self.runner = None
        self.site = None

        self.state = {
            "open": False,
            "entries": 0,
            "claims": 0,
            "end_timestamp": None,
            "winner": None,
        }
        self.state_lock = asyncio.Lock()

    async def handle_ws(self, request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        self.clients.add(ws)
        print("[OVERLAY] Client connected.")

        try:
            await ws.send_json({"type": "raffle_state", "state": await self.get_state()})
            async for _message in ws:
                pass
        finally:
            self.clients.discard(ws)
            print("[OVERLAY] Client disconnected.")

        return ws

    async def start(self):
        if WEBSOCKET_DISABLED:
            print("[OVERLAY] WebSocket server disabled by environment.")
            return

        if self.runner:
            return

        runner = web.AppRunner(self.app)

        try:
            await runner.setup()
            site = web.TCPSite(runner, self.host, self.port)
            await site.start()
        except Exception:
            await runner.cleanup()
            raise

        self.runner = runner
        self.site = site
        print(f"[OVERLAY] WebSocket server listening on ws://{self.host}:{self.port}/ws")

    async def stop(self):
        for ws in list(self.clients):
            await ws.close()
            print("[OVERLAY] Websocket server closed.")
        self.clients.clear()

        if self.runner:
            await self.runner.cleanup()
            self.runner = None
            self.site = None

    async def set_state(self, state):
        async with self.state_lock:
            self.state = dict(state)
            snapshot = dict(self.state)

        await self.broadcast({"type": "raffle_state", "state": snapshot})
        print("[OVERLAY] Pushing new raffle state to overlay.")  # might remove if too spammy

    async def get_state(self):
        async with self.state_lock:
            return dict(self.state)

    async def broadcast(self, payload):
        message = json.dumps(payload)

        for ws in list(self.clients):
            if ws.closed:
                self.clients.discard(ws)
                continue

            try:
                await ws.send_str(message)
            except Exception as exc:
                print(f"[OVERLAY] Failed to send websocket message: {exc}")
                self.clients.discard(ws)

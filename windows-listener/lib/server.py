import asyncio
import json
from .websocketServer import WebSocketServer
from .bleManager import BleakManager
from .helper import logging


class Server(WebSocketServer):
    logger = logging.getLogger(__name__)

    ble: BleakManager | None = None
    clients = set()
    tasks = {}
    loop: asyncio.AbstractEventLoop | None = None

    @classmethod
    def init_loop(cls, loop):
        cls.loop = loop

    async def on_connect(self, ws):
        Server.logger.info("Client connected")
        Server.clients.add(ws)
        Server.tasks[ws] = []

        task = asyncio.create_task(self._ble_status_heartbeat(ws))
        Server.tasks[ws].append(task)

    async def on_disconnect(self, ws):
        Server.logger.info("Client disconnected")
        Server.clients.discard(ws)

        if ws in Server.tasks:
            for t in Server.tasks[ws]:
                t.cancel()
            del Server.tasks[ws]

    async def on_message(self, ws, message):
        Server.logger.debug(message)

        try:
            data = json.loads(message)
            event = data.get("event")

            if event == "ble-scan":
                Server.ble = BleakManager()
                devices = await Server.ble.scan()

                await self.send(ws, {
                    "event": "ble-scan-result",
                    "data": [
                        {"name": d.name or "Unknown", "address": d.address}
                        for d in devices
                    ]
                })

            elif event == "ble-connect":
                address = data.get("address")

                if not Server.ble:
                    Server.ble = BleakManager()

                Server.ble.set_disconnect_callback(
                    lambda: asyncio.create_task(
                        self._on_ble_disconnected(ws)
                    )
                )

                success = await Server.ble.connect(address)

                await self.send(ws, {
                    "event": "ble-connect-result",
                    "connected": success,
                    "name": Server.ble.get_connected_name(),
                    "address": Server.ble.get_connected_address()
                })

            elif event == "ble-disconnect":
                if Server.ble:
                    await Server.ble.disconnect(clean=True)
                    Server.ble = None

                await self.send(ws, {
                    "event": "ble-disconnect-result",
                    "success": True
                })

        except Exception as e:
            Server.logger.error(e)

    async def disconnect_ble(self):
        if Server.ble:
            await Server.ble.disconnect(clean=True)
            Server.ble = None

    async def _ble_status_heartbeat(self, ws):
        try:
            while True:
                await asyncio.sleep(1)

                connected = False
                name = "Unknown"
                address = None

                if Server.ble:
                    connected = Server.ble.is_connected()
                    name = Server.ble.get_connected_name()
                    address = Server.ble.get_connected_address()

                await self.send(ws, {
                    "event": "ble-status-result",
                    "connected": connected,
                    "name": name,
                    "address": address
                })

        except asyncio.CancelledError:
            pass

    async def _on_ble_disconnected(self, ws):
        await self.send(ws, {
            "event": "ble-status-result",
            "connected": False,
            "name": "Unknown",
            "address": None
        })

    @classmethod
    def publish(cls, payload: dict):
        """
        Dipanggil dari main / thread lain
        """
        if not cls.loop:
            return

        async def _send_all():
            # Send to WebSocket clients
            for ws in list(cls.clients):
                try:
                    await cls().send(ws, payload)
                except Exception as e:
                    cls.logger.error(e)
            
            # Send to BLE device if connected
            if cls.ble and cls.ble.is_connected() and cls.ble.write_char is not None:
                try:
                    await cls.ble.write_json(payload)
                except Exception as e:
                    cls.logger.error(f"BLE write error: {e}")

        asyncio.run_coroutine_threadsafe(_send_all(), cls.loop)

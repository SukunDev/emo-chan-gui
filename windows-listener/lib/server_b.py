from .websocketServer import WebSocketServer
from .bleManager import BleakManager
from .listener import MediaPlaybackListener, MessageNotificationListener, AudioAmplitudeListener
import json
import asyncio
from .helper import logging


class Server(WebSocketServer):
    ble = BleakManager()
    tasks = {}  # ws → list of asyncio Tasks
    windows_listener_task = {}  # ws → list of asyncio Tasks
    name = "Server"
    logger = logging.getLogger(__name__)

    # FIX ✓ tidak pakai comma (bukan tuple lagi)
    media_interval: float = 2.0
    message_interval: float = 2.0
    audio_interval: float = 0.033

    enable_audio: bool = True

    media_listener = MediaPlaybackListener()
    message_listener = MessageNotificationListener()
    audio_listener = AudioAmplitudeListener() if enable_audio else None

    is_running = False

    # ---------------- CONNECT --------------------
    async def on_connect(self, ws):
        Server.logger.info("Client joined")
        Server.tasks[ws] = []
        Server.windows_listener_task[ws] = []

        task = asyncio.create_task(self._ble_status_result_heartbeat(ws))
        Server.tasks[ws].append(task)
        Server.ble.set_disconnect_callback(lambda: asyncio.create_task(self._on_ble_disconnected(ws)))


    # ---------------- MESSAGE --------------------
    async def on_message(self, ws, message):
        Server.logger.debug(f"Client says: {message}")

        try:
            data = json.loads(message)
            event = data.get("event")

            # -------- Scan ----------
            if event == "ble-scan":
                devices = await Server.ble.scan()
                result = [{"name": d.name or "Unknown", "address": d.address} for d in devices]

                await self.send(ws, {
                    "event": "ble-scan-result",
                    "data": result
                })

            # -------- Connect --------
            elif event == "ble-connect":
                address = data.get("address")
                Server.logger.info(f"BLE connect request: {address}")

                success = await Server.ble.connect(address)

                await self.send(ws, {
                    "event": "ble-connect-result",
                    "connected": success,
                    "name": Server.ble.get_connected_name(),
                    "address": Server.ble.get_connected_address()
                })

                # Start listeners
                task = asyncio.create_task(self._start_listen_windows_event(ws))
                Server.windows_listener_task[ws].append(task)

            # -------- Disconnect --------
            elif event == "ble-disconnect":
                Server.logger.info("BLE disconnect request")
                await Server.ble.disconnect()

                await self.send(ws, {"event": "ble-disconnect-result"})

            # -------- Status --------
            elif event == "ble-status":
                await self.send(ws, {
                    "event": "ble-status-result",
                    "connected": Server.ble.is_connected(),
                    "name": Server.ble.get_connected_name(),
                    "address": Server.ble.get_connected_address()
                })

        except Exception as e:
            Server.logger.error(f"Error handling message: {e}")

    # ---------------- DISCONNECT --------------------
    async def on_disconnect(self, ws):
        Server.logger.info("Client disconnected")

        if ws in Server.tasks:
            for t in Server.tasks[ws]:
                t.cancel()
            del Server.tasks[ws]
        if ws in Server.windows_listener_task:
            for t in Server.windows_listener_task[ws]:
                t.cancel()
            del Server.windows_listener_task[ws]

    # ---------------- HEARTBEAT --------------------
    async def _ble_status_result_heartbeat(self, ws):
        try:
            while True:
                await asyncio.sleep(1)

                await self.send(ws, {
                    "event": "ble-status-result",
                    "connected": Server.ble.is_connected(),
                    "name": Server.ble.get_connected_name(),
                    "address": Server.ble.get_connected_address()
                })

        except asyncio.CancelledError:
            Server.logger.debug("Heartbeat task cancelled")
        except Exception as e:
            Server.logger.error(f"Heartbeat error: {e}")

    # ---------------- LISTENERS --------------------
    async def _start_listen_windows_event(self, ws):
        Server.is_running = True
        await Server.media_listener.start()
        await Server.message_listener.start()
        if Server.audio_listener:
            await Server.audio_listener.start()

        Server.logger.info("All systems started")

        # Add tasks properly
        Server.windows_listener_task[ws].append(asyncio.create_task(self._monitor_media()))
        Server.windows_listener_task[ws].append(asyncio.create_task(self._monitor_messages()))

        if Server.audio_listener:
            Server.windows_listener_task[ws].append(asyncio.create_task(self._monitor_audio()))

    # ---------------- MONITORS --------------------
    async def _monitor_media(self):
        while Server.is_running:
            try:
                events = await Server.media_listener.get_events()
                for event in events:
                    Server.logger.info(f"Media event: {event.title} - {event.status}")
                    if Server.ble.is_connected():
                        await Server.ble.write_json(event)
            except Exception as e:
                Server.logger.error(f"Error in media monitor: {e}")

            await asyncio.sleep(Server.media_interval)

    async def _monitor_messages(self):
        while Server.is_running:
            try:
                events = await Server.message_listener.get_events()
                for event in events:
                    Server.logger.info(f"Message event: {event.app} - {event.title}")
                    if Server.ble.is_connected():
                        await Server.ble.write_json(event)
            except Exception as e:
                Server.logger.error(f"Error in message monitor: {e}")

            await asyncio.sleep(Server.message_interval)

    async def _monitor_audio(self):
        while Server.is_running:
            try:
                events = await Server.audio_listener.get_events()
                for event in events:
                    if event.amplitude > 0.01:
                        if Server.ble.is_connected():
                            await Server.ble.write_json(event)
            except Exception as e:
                Server.logger.error(f"Error in audio monitor: {e}")

            await asyncio.sleep(Server.audio_interval)
            
    async def _on_ble_disconnected(self, ws):
        Server.logger.warning("BLE disconnected (callback)")

        # kirim ke client
        await self.send(ws, {
            "event": "ble-status-result",
            "connected": False,
            "name": None,
            "address": None
        })

        # stop semua listener
        if ws in Server.windows_listener_task:
            for t in Server.windows_listener_task[ws]:
                t.cancel()
            Server.windows_listener_task[ws] = []

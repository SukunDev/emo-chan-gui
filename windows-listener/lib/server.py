from .websocketServer import WebSocketServer
from .bleManager import BleakManager
from .listener import MediaPlaybackListener, AudioAmplitudeListener, MediaAudioEvent
import json
import asyncio
from .helper import logging


class Server(WebSocketServer):
    ble = None
    tasks = {}
    windows_listener_tasks = {}
    logger = logging.getLogger(__name__)

    enable_audio = True
    media_listener = MediaPlaybackListener()
    audio_listener = AudioAmplitudeListener() if enable_audio else None
    
    update_interval = 0.1
    amplitude_threshold = 0.01
    is_running = False
    last_media_state = None
    last_sent_unknown = False
    
    async def on_connect(self, ws):
        Server.logger.info("Client joined")
        Server.tasks[ws] = []

        task = asyncio.create_task(self._ble_status_result_heartbeat(ws))
        Server.tasks[ws].append(task)

    async def on_message(self, ws, message):
        Server.logger.debug(f"Client says: {message}")

        try:
            data = json.loads(message)
            event = data.get("event")
            
            if event == "ble-scan":
                # Buat instance baru untuk scan
                Server.logger.info("Creating fresh BLE instance for scan")
                Server.ble = BleakManager()
                
                devices = await Server.ble.scan()
                result = [{"name": d.name or "Unknown", "address": d.address} for d in devices]

                await self.send(ws, {
                    "event": "ble-scan-result",
                    "data": result
                })
                
            elif event == "ble-connect":
                address = data.get("address")
                Server.logger.info(f"BLE connect request: {address}")

                # Pastikan ada instance BLE
                if Server.ble is None:
                    Server.logger.info("Creating fresh BLE instance for connect")
                    Server.ble = BleakManager()

                # Set callback untuk disconnect events
                Server.ble.set_disconnect_callback(
                    lambda: asyncio.create_task(self._on_ble_disconnected(ws))
                )

                success = await Server.ble.connect(address)
                if Server.is_running is False:
                    Server.is_running = True
                    await Server.media_listener.start()
                    if self.audio_listener:
                        await self.audio_listener.start()

                    Server.windows_listener_tasks[ws] = []
                    window_monitor_task = asyncio.create_task(self._window_monitor_loop(ws))
                    Server.windows_listener_tasks[ws].append(window_monitor_task)

                await self.send(ws, {
                    "event": "ble-connect-result",
                    "connected": success,
                    "name": Server.ble.get_connected_name(),
                    "address": Server.ble.get_connected_address()
                })

            elif event == "ble-disconnect":
                Server.logger.info("BLE manual disconnect request")
                
                if Server.ble:
                    # Manual disconnect - clean=True
                    await Server.ble.disconnect(clean=True)
                    
                    # Hapus instance completely
                    Server.ble = None
                    Server.logger.info("BLE instance destroyed")

                await self.send(ws, {
                    "event": "ble-disconnect-result",
                    "success": True
                })
                
            elif event == "ble-status":
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

        except Exception as e:
            Server.logger.error(f"Error handling message: {e}")
            
    async def on_disconnect(self, ws):
        Server.logger.info("Client disconnected")

        if ws in Server.tasks:
            for t in Server.tasks[ws]:
                t.cancel()
            del Server.tasks[ws]

        if ws in Server.windows_listener_tasks:
            for t in Server.windows_listener_tasks[ws]:
                t.cancel()
            del Server.windows_listener_tasks[ws]
            
    async def _ble_status_result_heartbeat(self, ws):
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
            Server.logger.debug("Heartbeat task cancelled")
        except Exception as e:
            Server.logger.error(f"Heartbeat error: {e}")

    async def _window_monitor_loop(self, ws):
        """Main monitoring loop"""
        first_run = True
        last_log_time = 0
        print("monitor")
        
        while Server.is_running:
            try:
                title, artist, status, is_playing = await Server.media_listener.get_current_media()
                
                audio_data = {"amplitude": 0.0, "peak": 0.0, "rms": 0.0}
                if Server.audio_listener:
                    audio_data = Server.audio_listener.get_current_amplitude()

                print(audio_data)
                
                event = MediaAudioEvent(
                    title=title,
                    artist=artist,
                    status=status,
                    is_playing=is_playing,
                    audio_amplitude=audio_data
                )
                
                current_media_state = (title, artist, status)
                media_changed = current_media_state != Server.last_media_state
                audio_significant = audio_data["amplitude"] > Server.amplitude_threshold
                
                media_unknown = (title == "Unknown" and artist == "Unknown")
                
                should_broadcast = False
                
                if first_run:
                    should_broadcast = True
                    first_run = False
                    Server.logger.info(f"Initial state: {title} by {artist} - {status} (amp: {audio_data['amplitude']:.2f})")
                    Server.last_media_state = current_media_state
                    Server.last_sent_unknown = media_unknown
                
                elif media_changed:
                    should_broadcast = True
                    if not media_unknown:
                        Server.logger.info(f"Media: {title} by {artist} - {status}")
                    elif not Server.last_sent_unknown:
                        Server.logger.info(f"Media: Unknown - Audio amplitude: {audio_data['amplitude']:.2f}")
                    Server.last_media_state = current_media_state
                    Server.last_sent_unknown = media_unknown
                
                # 🔥 PERBAIKAN: Kirim jika ada audio meskipun media Unknown
                elif audio_significant:
                    should_broadcast = True
                    
                    import time
                    current_time = time.time()
                    if (current_time - last_log_time) > 5:
                        if media_unknown:
                            Server.logger.info(f"Audio only - amp: {audio_data['amplitude']:.2f}, peak: {audio_data['peak']:.2f}")
                        else:
                            Server.logger.info(f"Audio active ({title}) - amp: {audio_data['amplitude']:.2f}")
                        last_log_time = current_time
                
                # Kirim data
                if should_broadcast:
                    json_data = event.to_json() if hasattr(event, 'to_json') else json.dumps(event)
                    await self.send(ws, json_data)
                    if Server.ble is not None and Server.ble.is_connected():
                        await Server.ble.write_json(event)
                
            except Exception as e:
                print(e)
                Server.logger.error(f"Error in monitor loop: {e}")
            
            await asyncio.sleep(Server.update_interval)

    async def _on_ble_disconnected(self, ws):
        """
        Callback saat BLE disconnect (unexpected)
        """
        Server.logger.warning("BLE disconnected (callback triggered)")
        
        connected = False
        name = "Unknown"
        address = None
        
        if Server.ble:
            connected = Server.ble.is_connected()
            name = Server.ble.get_connected_name()
            address = Server.ble.get_connected_address()
        
        # Kirim status update ke client
        await self.send(ws, {
            "event": "ble-status-result",
            "connected": connected,
            "name": name,
            "address": address
        })
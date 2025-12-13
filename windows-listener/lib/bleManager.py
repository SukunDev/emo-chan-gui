from bleak import BleakScanner, BleakClient
from .helper import logging
import json
import asyncio

class BleakManager:
    def __init__(self):
        self.client: BleakClient | None = None
        self.connected_address: str | None = None
        self.connected_name: str | None = None
        self.last_scan_result = []

        self.write_char = None
        self.notify_char = None

        self.should_reconnect = False
        self.reconnect_task = None
        self.disconnect_callback = None

        self.logger = logging.getLogger(__name__)

    async def scan(self):
        try:
            self.logger.info("Scanning BLE devices...")
            devices = await BleakScanner.discover(timeout=5)

            if not devices:
                self.last_scan_result = []
                self.logger.warning("Tidak ada perangkat ditemukan.")
                return []

            self.last_scan_result = devices
            return devices

        except Exception as e:
            self.logger.error(f"Scan error: {e}")
            return []

    async def connect(self, address: str):
        try:
            if self.client and self.client.is_connected:
                await self.disconnect(clean=True)

            self.client = BleakClient(address, disconnected_callback=self._on_disconnect_event)

            await self.client.connect()

            if not self.client.is_connected:
                self.logger.error("Gagal connect.")
                return False

            self.connected_address = address
            self.connected_name = self._resolve_name(address)
            self.should_reconnect = True

            self.logger.info(f"Connected: {self.connected_name} ({address})")

            self._discover_characteristics()
            return True

        except Exception as e:
            self.logger.error(f"Connect error: {e}")
            return False

    def _discover_characteristics(self):
        self.write_char = None
        self.notify_char = None

        self.logger.info("Discovering services & characteristics...")

        for service in self.client.services:
            for char in service.characteristics:
                props = char.properties

                if "write" in props and self.write_char is None:
                    self.write_char = char.uuid

                if "notify" in props and self.notify_char is None:
                    self.notify_char = char.uuid

        self.logger.info(f"Write char  : {self.write_char}")
        self.logger.info(f"Notify char : {self.notify_char}")

    async def write(self, text: str):
        if not self.write_char:
            self.logger.error("Tidak ada characteristic write!")
            return False

        try:
            await self.client.write_gatt_char(
                self.write_char,
                text.encode(),
                response=False,
            )
            return True

        except Exception as e:
            self.logger.error(f"Write error: {e}")
            return False

    async def write_json(self, data: dict):
        if not self.write_char:
            self.logger.error("Tidak ada characteristic write!")
            return False

        try:
            json_data = data.to_json() if hasattr(data, 'to_json') else json.dumps(data)

            await self.client.write_gatt_char(
                self.write_char,
                json_data.encode("utf-8"),
                response=False
            )

            self.logger.debug(f"Sent JSON: {json_data}")
            return True

        except Exception as e:
            self.logger.error(f"Write JSON error: {e}")
            return False

    async def start_notify(self, handler):
        if not self.notify_char:
            self.logger.error("Tidak ada characteristic notify!")
            return False

        try:
            await self.client.start_notify(self.notify_char, handler)
            self.logger.info(f"Notify aktif pada {self.notify_char}")
            return True

        except Exception as e:
            self.logger.error(f"Notify error: {e}")
            return False

    async def stop_notify(self):
        if self.notify_char:
            try:
                await self.client.stop_notify(self.notify_char)
            except:
                pass

    async def disconnect(self, clean: bool = True):
        """
        Disconnect dari BLE device
        
        Args:
            clean: True = manual disconnect (bersihkan semua), 
                   False = unexpected disconnect (siapkan reconnect)
        """
        try:
            if self.reconnect_task and not self.reconnect_task.done():
                self.reconnect_task.cancel()
                self.reconnect_task = None

            if self.client and self.client.is_connected:
                await self.stop_notify()
                await self.client.disconnect()

            if clean:
                self.logger.info("Clean disconnect - clearing all state")
                self.should_reconnect = False
                self.client = None
                self.connected_address = None
                self.connected_name = None
                self.write_char = None
                self.notify_char = None
            else:
                self.logger.warning("Unexpected disconnect - keeping state for reconnect")
                self.client = None

        except Exception as e:
            self.logger.error(f"Disconnect error: {e}")

    def _on_disconnect_event(self, client: BleakClient):
        """Callback saat BLE server disconnect"""
        self.logger.warning(f"BLE server disconnected: {self.connected_name}")
        
        if self.disconnect_callback:
            asyncio.create_task(self._handle_disconnect())

    async def _handle_disconnect(self):
        """Handle unexpected disconnect"""
        if self.disconnect_callback:
            self.disconnect_callback()
        
        if self.should_reconnect and self.connected_address:
            self.logger.info("Starting auto-reconnect...")
            self.reconnect_task = asyncio.create_task(self._auto_reconnect())

    async def _auto_reconnect(self):
        """Auto-reconnect ke BLE server"""
        retry_count = 0
        
        while self.should_reconnect and self.connected_address:
            try:
                retry_count += 1
                interval = 2
                
                self.logger.info(f"Reconnect attempt #{retry_count} in {interval}s...")
                await asyncio.sleep(interval)

                self.client = BleakClient(
                    self.connected_address, 
                    disconnected_callback=self._on_disconnect_event
                )
                
                await self.client.connect()

                if self.client.is_connected:
                    self.logger.info(f"Reconnected successfully to {self.connected_name}")
                    
                    self._discover_characteristics()
                    
                    if self.disconnect_callback:
                        self.disconnect_callback()
                    
                    

            except Exception as e:
                self.logger.debug(f"Reconnect failed: {e}")
                self.client = None
                continue

    def set_disconnect_callback(self, callback):
        """Set callback untuk disconnect event"""
        self.disconnect_callback = callback

    def is_connected(self) -> bool:
        connected = self.client is not None and self.client.is_connected
        self.logger.debug(f"BLE connected status: {connected}")
        return connected

    def get_connected_address(self):
        return self.connected_address

    def get_connected_name(self):
        return self.connected_name or "Unknown"

    def _resolve_name(self, address: str) -> str:
        for dev in self.last_scan_result:
            if dev.address == address:
                self.logger.debug(f"Resolved name for {address}: {dev.name or 'Unknown'}")
                return dev.name or "Unknown"
        self.logger.debug(f"Name for {address} tidak ditemukan di cached scan.")
        return "Unknown"
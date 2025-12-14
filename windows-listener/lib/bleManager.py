from bleak import BleakScanner, BleakClient
from .helper import logging
import json
import asyncio
import sys
import threading
from typing import Optional

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
        
        # Thread dan loop untuk BLE operations
        self._ble_thread: Optional[threading.Thread] = None
        self._ble_loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread_started = threading.Event()

    def _ensure_ble_thread(self):
        """Pastikan BLE thread sudah running"""
        if self._ble_thread is None or not self._ble_thread.is_alive():
            self._thread_started.clear()
            self._ble_thread = threading.Thread(
                target=self._run_ble_loop, 
                daemon=True,
                name="BLE-Thread"
            )
            self._ble_thread.start()
            # Wait untuk thread siap (max 5 detik)
            if not self._thread_started.wait(timeout=5):
                raise RuntimeError("BLE thread failed to start")

    def _run_ble_loop(self):
        """Run event loop khusus untuk BLE di thread terpisah"""
        try:
            # Set WindowsSelectorEventLoopPolicy untuk Bleak
            if sys.platform == 'win32':
                asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
            
            # Create dan set loop baru
            self._ble_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._ble_loop)
            
            # Signal bahwa thread sudah ready
            self._thread_started.set()
            
            # Run loop forever
            self._ble_loop.run_forever()
            
        except Exception as e:
            self.logger.error(f"BLE loop error: {e}")
        finally:
            try:
                self._ble_loop.close()
            except:
                pass
            self._ble_loop = None

    async def _run_in_ble_loop(self, coro):
        """
        Execute coroutine di BLE loop secara async (non-blocking)
        Returns: awaitable future
        """
        self._ensure_ble_thread()
        
        # Schedule coroutine di BLE loop dan return future
        future = asyncio.run_coroutine_threadsafe(coro, self._ble_loop)
        
        # Wrap future dalam asyncio.Future untuk bisa di-await
        loop = asyncio.get_event_loop()
        result_future = loop.create_future()
        
        def callback(fut):
            try:
                result = fut.result()
                loop.call_soon_threadsafe(result_future.set_result, result)
            except Exception as e:
                loop.call_soon_threadsafe(result_future.set_exception, e)
        
        future.add_done_callback(callback)
        return await result_future

    async def scan(self):
        """Scan BLE devices"""
        try:
            self.logger.info("Scanning BLE devices...")
            
            # Run scan di BLE thread (non-blocking)
            devices = await self._run_in_ble_loop(
                BleakScanner.discover(timeout=5)
            )

            if not devices:
                self.last_scan_result = []
                self.logger.warning("Tidak ada perangkat ditemukan.")
                return []

            self.last_scan_result = devices
            self.logger.info(f"Found {len(devices)} device(s)")
            return devices

        except Exception as e:
            self.logger.error(f"Scan error: {e}")
            import traceback
            traceback.print_exc()
            return []

    async def connect(self, address: str):
        """Connect to BLE device"""
        try:
            if self.client and self.client.is_connected:
                await self.disconnect(clean=True)

            # Connect di BLE thread
            success = await self._run_in_ble_loop(
                self._connect_impl(address)
            )
            
            return success

        except Exception as e:
            self.logger.error(f"Connect error: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def _connect_impl(self, address: str):
        """Implementation connect (runs in BLE thread)"""
        self.client = BleakClient(
            address, 
            disconnected_callback=self._on_disconnect_event
        )
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

    def _discover_characteristics(self):
        """Discover GATT characteristics"""
        self.write_char = None
        self.notify_char = None

        if not self.client:
            return

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
        """Write text to BLE device"""
        if not self.write_char:
            self.logger.error("Tidak ada characteristic write!")
            return False

        try:
            await self._run_in_ble_loop(
                self.client.write_gatt_char(
                    self.write_char,
                    text.encode(),
                    response=False,
                )
            )
            return True

        except Exception as e:
            self.logger.error(f"Write error: {e}")
            return False

    async def write_json(self, data: dict):
        """Write JSON data to BLE device"""
        if not self.write_char:
            self.logger.error("Tidak ada characteristic write!")
            return False

        try:
            json_data = data if isinstance(data, str) else json.dumps(data)
            
            await self._run_in_ble_loop(
                self.client.write_gatt_char(
                    self.write_char,
                    json_data.encode("utf-8"),
                    response=False
                )
            )

            self.logger.debug(f"Sent JSON: {json_data}")
            return True

        except Exception as e:
            self.logger.error(f"Write JSON error: {e}")
            return False

    async def start_notify(self, handler):
        """Start notifications"""
        if not self.notify_char:
            self.logger.error("Tidak ada characteristic notify!")
            return False

        try:
            await self._run_in_ble_loop(
                self.client.start_notify(self.notify_char, handler)
            )
            self.logger.info(f"Notify aktif pada {self.notify_char}")
            return True

        except Exception as e:
            self.logger.error(f"Notify error: {e}")
            return False

    async def stop_notify(self):
        """Stop notifications"""
        if self.notify_char and self.client:
            try:
                await self._run_in_ble_loop(
                    self.client.stop_notify(self.notify_char)
                )
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
            # Cancel reconnect task
            if self.reconnect_task and not self.reconnect_task.done():
                self.reconnect_task.cancel()
                try:
                    await self.reconnect_task
                except asyncio.CancelledError:
                    pass
                self.reconnect_task = None

            # Disconnect dari device
            if self.client and self.client.is_connected:
                await self.stop_notify()
                
                await self._run_in_ble_loop(
                    self.client.disconnect()
                )

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
        """Callback saat BLE server disconnect (called from BLE thread)"""
        self.logger.warning(f"BLE server disconnected: {self.connected_name}")
        
        # Schedule handler di main loop
        if self.disconnect_callback:
            try:
                # Get main loop and schedule callback
                import asyncio
                main_loop = asyncio.get_event_loop()
                if main_loop and main_loop.is_running():
                    main_loop.call_soon_threadsafe(
                        lambda: asyncio.create_task(self._handle_disconnect())
                    )
            except Exception as e:
                self.logger.warning(f"Cannot schedule disconnect handler: {e}")

    async def _handle_disconnect(self):
        """Handle unexpected disconnect (runs in main loop)"""
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

                # Reconnect di BLE thread
                success = await self._run_in_ble_loop(
                    self._reconnect_impl()
                )

                if success:
                    self.logger.info(f"Reconnected successfully to {self.connected_name}")
                    
                    if self.disconnect_callback:
                        self.disconnect_callback()
                    
                    break

            except Exception as e:
                self.logger.debug(f"Reconnect failed: {e}")
                self.client = None
                continue

    async def _reconnect_impl(self):
        """Implementation reconnect (runs in BLE thread)"""
        self.client = BleakClient(
            self.connected_address, 
            disconnected_callback=self._on_disconnect_event
        )
        
        await self.client.connect()

        if self.client.is_connected:
            self._discover_characteristics()
            return True
        
        return False

    def set_disconnect_callback(self, callback):
        """Set callback untuk disconnect event"""
        self.disconnect_callback = callback

    def is_connected(self) -> bool:
        """Check if connected to BLE device"""
        connected = self.client is not None and self.client.is_connected
        self.logger.debug(f"BLE connected status: {connected}")
        return connected

    def get_connected_address(self):
        """Get connected device address"""
        return self.connected_address

    def get_connected_name(self):
        """Get connected device name"""
        return self.connected_name or "Unknown"

    def _resolve_name(self, address: str) -> str:
        """Resolve device name from address"""
        for dev in self.last_scan_result:
            if dev.address == address:
                self.logger.debug(f"Resolved name for {address}: {dev.name or 'Unknown'}")
                return dev.name or "Unknown"
        self.logger.debug(f"Name for {address} tidak ditemukan di cached scan.")
        return "Unknown"
    
    def shutdown(self):
        """Cleanup BLE thread"""
        if self._ble_loop and self._ble_loop.is_running():
            self._ble_loop.call_soon_threadsafe(self._ble_loop.stop)
    
    def __del__(self):
        """Cleanup on deletion"""
        try:
            self.shutdown()
        except:
            pass
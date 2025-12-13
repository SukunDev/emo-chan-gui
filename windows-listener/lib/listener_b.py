"""
Windows 11 Event Listener dengan WebSocket
Mengirim event ke aplikasi Electron:
- Media playback events
- Message notifications
- Audio amplitude data
"""

import asyncio
import json
from datetime import datetime
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, List
import logging

# Media Control
from winsdk.windows.media.control import \
    GlobalSystemMediaTransportControlsSessionManager as MediaManager

# Window monitoring
import win32gui
import win32process
import psutil

# WebSocket
import websockets

# Audio capture
try:
    import pyaudio
    import numpy as np
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False
    print("⚠️  PyAudio/NumPy tidak tersedia. Audio amplitude dinonaktifkan.")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ==================== Data Models ====================

@dataclass
class MediaEvent:
    """Model untuk media playback event"""
    type: str = "media"
    timestamp: str = ""
    app_id: str = ""
    app_name: str = ""
    title: str = ""
    artist: str = ""
    album: str = ""
    status: str = ""
    is_playing: bool = False
    
    def to_json(self) -> str:
        return json.dumps(asdict(self))


@dataclass
class MessageEvent:
    """Model untuk message notification event"""
    type: str = "message"
    timestamp: str = ""
    app: str = ""
    app_id: str = ""
    title: str = ""
    has_notification: bool = False
    notification_count: str = "0"
    
    def to_json(self) -> str:
        return json.dumps(asdict(self))


@dataclass
class AudioAmplitudeEvent:
    """Model untuk audio amplitude event"""
    type: str = "audio_amplitude"
    timestamp: str = ""
    amplitude: float = 0.0
    peak: float = 0.0
    rms: float = 0.0
    
    def to_json(self) -> str:
        return json.dumps(asdict(self))


@dataclass
class SystemEvent:
    """Model untuk system event (connection, error, dll)"""
    type: str = "system"
    timestamp: str = ""
    event: str = ""
    message: str = ""
    data: Optional[Dict[str, Any]] = None
    
    def to_json(self) -> str:
        return json.dumps(asdict(self))


# ==================== Base Classes ====================

class EventListener(ABC):
    """Base class untuk semua listener"""
    
    def __init__(self, name: str):
        self.name = name
        self.is_running = False
        self.logger = logging.getLogger(f"{__name__}.{name}")
    
    @abstractmethod
    async def start(self):
        """Start listening"""
        pass
    
    @abstractmethod
    async def stop(self):
        """Stop listening"""
        pass
    
    @abstractmethod
    async def get_events(self) -> List[Any]:
        """Get current events"""
        pass


# ==================== Media Listener ====================

class MediaPlaybackListener(EventListener):
    """Listener untuk media playback"""
    
    APP_NAME_MAP = {
        'spotify': 'Spotify',
        'chrome': 'Browser (YouTube/Web)',
        'msedge': 'Browser (YouTube/Web)',
        'vlc': 'VLC Media Player',
        'windows.media': 'Windows Media Player',
        'firefox': 'Firefox Browser',
    }
    
    def __init__(self):
        super().__init__("MediaPlaybackListener")
        self.last_media_state = None
    
    async def start(self):
        """Start media listener"""
        self.is_running = True
        self.logger.info("Media playback listener started")
    
    async def stop(self):
        """Stop media listener"""
        self.is_running = False
        self.logger.info("Media playback listener stopped")
    
    async def get_events(self) -> List[MediaEvent]:
        """Get current media playback state"""
        if not self.is_running:
            return []
        
        try:
            sessions = await MediaManager.request_async()
            current_session = sessions.get_current_session()
            
            if not current_session:
                return []
            
            info = await current_session.try_get_media_properties_async()
            playback_info = current_session.get_playback_info()
            
            # Map playback status
            status_map = {
                0: 'Closed', 1: 'Opened', 2: 'Changing',
                3: 'Stopped', 4: 'Playing', 5: 'Paused'
            }
            
            app_id = current_session.source_app_user_model_id
            status = status_map.get(playback_info.playback_status, 'Unknown')
            
            media_event = MediaEvent(
                timestamp=datetime.now().isoformat(),
                app_id=app_id,
                app_name=self._detect_app_name(app_id),
                title=info.title or "",
                artist=info.artist or "",
                album=info.album_title or "",
                status=status,
                is_playing=(playback_info.playback_status == 4)
            )
            
            # Only return if state changed
            current_state = (media_event.title, media_event.status)
            if current_state != self.last_media_state:
                self.last_media_state = current_state
                return [media_event]
            
            return []
            
        except Exception as e:
            self.logger.error(f"Error getting media info: {e}")
            return []
    
    def _detect_app_name(self, app_id: str) -> str:
        """Detect app name from app ID"""
        app_id_lower = app_id.lower()
        for key, name in self.APP_NAME_MAP.items():
            if key in app_id_lower:
                return name
        return app_id


# ==================== Message Listener ====================

class MessageNotificationListener(EventListener):
    """Listener untuk message notifications"""
    
    TRACKED_APPS = {
        'whatsapp.exe': {'name': 'WhatsApp', 'pattern': r'\((\d+)\)'},
        'discord.exe': {'name': 'Discord', 'pattern': r'\((\d+)\)'},
        'telegram.exe': {'name': 'Telegram', 'pattern': r'\((\d+)\)'},
        'signal.exe': {'name': 'Signal', 'pattern': r'\((\d+)\)'},
        'slack.exe': {'name': 'Slack', 'pattern': r'\((\d+)\)'},
        'teams.exe': {'name': 'Microsoft Teams', 'pattern': r'\((\d+)\)'},
    }
    
    def __init__(self):
        super().__init__("MessageNotificationListener")
        self.last_window_titles: Dict[str, str] = {}
    
    async def start(self):
        """Start message listener"""
        self.is_running = True
        self.logger.info("Message notification listener started")
    
    async def stop(self):
        """Stop message listener"""
        self.is_running = False
        self.logger.info("Message notification listener stopped")
    
    async def get_events(self) -> List[MessageEvent]:
        """Get message notification events"""
        if not self.is_running:
            return []
        
        events = []
        
        def enum_callback(hwnd, extra):
            if not win32gui.IsWindowVisible(hwnd):
                return
            
            title = win32gui.GetWindowText(hwnd)
            if not title:
                return
            
            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                process = psutil.Process(pid)
                process_name = process.name().lower()
                
                # Check if this is a tracked app
                if process_name in self.TRACKED_APPS:
                    app_info = self.TRACKED_APPS[process_name]
                    title_key = f"{process_name}_{hwnd}"
                    
                    # Check if title changed
                    if title_key not in self.last_window_titles or \
                       self.last_window_titles[title_key] != title:
                        
                        import re
                        match = re.search(app_info['pattern'], title)
                        
                        message_event = MessageEvent(
                            timestamp=datetime.now().isoformat(),
                            app=app_info['name'],
                            app_id=process_name,
                            title=title,
                            has_notification=match is not None,
                            notification_count=match.group(1) if match else "0"
                        )
                        
                        events.append(message_event)
                        self.last_window_titles[title_key] = title
                        
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        try:
            win32gui.EnumWindows(enum_callback, None)
        except Exception as e:
            self.logger.error(f"Error enumerating windows: {e}")
        
        return events


# ==================== Audio Amplitude Listener ====================

class AudioAmplitudeListener(EventListener):
    """Listener untuk audio amplitude"""
    
    def __init__(self, chunk_size: int = 512, sample_rate: int = 44100):  # Smaller chunk = more responsive
        super().__init__("AudioAmplitudeListener")
        self.chunk_size = chunk_size
        self.sample_rate = sample_rate
        self.audio_data = np.zeros(chunk_size) if AUDIO_AVAILABLE else None
        self.pyaudio_instance = None
        self.stream = None
        self.available = AUDIO_AVAILABLE
    
    async def start(self):
        """Start audio capture"""
        if not self.available:
            self.logger.warning("Audio capture not available")
            return
        
        self.is_running = True
        
        try:
            self.pyaudio_instance = pyaudio.PyAudio()
            device_index = self._find_loopback_device()
            
            self.stream = self.pyaudio_instance.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.sample_rate,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=self.chunk_size,
                stream_callback=self._audio_callback
            )
            
            self.stream.start_stream()
            self.logger.info(f"Audio capture started (device: {device_index})")
            
        except Exception as e:
            self.logger.error(f"Failed to start audio capture: {e}")
            self.is_running = False
    
    async def stop(self):
        """Stop audio capture"""
        self.is_running = False
        
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        
        if self.pyaudio_instance:
            self.pyaudio_instance.terminate()
        
        self.logger.info("Audio capture stopped")
    
    async def get_events(self) -> List[AudioAmplitudeEvent]:
        """Get current audio amplitude"""
        if not self.is_running or self.audio_data is None:
            return []
        
        try:
            # Calculate amplitude metrics with safety checks
            audio_abs = np.abs(self.audio_data)
            
            # Avoid division by zero and invalid operations
            amplitude = float(audio_abs.mean()) / 32768.0 if len(audio_abs) > 0 else 0.0
            peak = float(audio_abs.max()) / 32768.0 if len(audio_abs) > 0 else 0.0
            
            # Safe RMS calculation
            if len(self.audio_data) > 0:
                audio_squared = self.audio_data.astype(np.float64) ** 2
                mean_squared = np.mean(audio_squared)
                if mean_squared >= 0:
                    rms = float(np.sqrt(mean_squared)) / 32768.0
                else:
                    rms = 0.0
            else:
                rms = 0.0
            
            event = AudioAmplitudeEvent(
                timestamp=datetime.now().isoformat(),
                amplitude=amplitude,
                peak=peak,
                rms=rms
            )
            
            return [event]
            
        except Exception as e:
            self.logger.error(f"Error calculating amplitude: {e}")
            return []
    
    def _audio_callback(self, in_data, frame_count, time_info, status):
        """Callback for audio data"""
        if self.is_running:
            self.audio_data = np.frombuffer(in_data, dtype=np.int16)
        return (in_data, pyaudio.paContinue)
    
    def _find_loopback_device(self) -> Optional[int]:
        """Find loopback device for system audio"""
        for i in range(self.pyaudio_instance.get_device_count()):
            dev_info = self.pyaudio_instance.get_device_info_by_index(i)
            name = dev_info.get('name', '').lower()
            if any(keyword in name for keyword in ['stereo mix', 'loopback', 'what u hear']):
                if dev_info.get('maxInputChannels', 0) > 0:
                    return i
        return None


# ==================== WebSocket Server ====================

class WebSocketEventServer:
    """WebSocket server untuk mengirim events ke Electron app"""
    
    def __init__(self, host: str = "localhost", port: int = 8765):
        self.host = host
        self.port = port
        self.clients = set()
        self.logger = logging.getLogger(f"{__name__}.WebSocketServer")
        self.server = None
    
    async def start(self):
        """Start WebSocket server"""
        async def handler(websocket):
            await self._handle_client(websocket)
        
        self.server = await websockets.serve(
            handler,
            self.host,
            self.port
        )
        self.logger.info(f"WebSocket server started on ws://{self.host}:{self.port}")
    
    async def stop(self):
        """Stop WebSocket server"""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        self.logger.info("WebSocket server stopped")
    
    async def _handle_client(self, websocket):
        """Handle new client connection"""
        self.clients.add(websocket)
        client_addr = websocket.remote_address
        self.logger.info(f"Client connected: {client_addr}")
        
        # Send connection event
        event = SystemEvent(
            timestamp=datetime.now().isoformat(),
            event="connected",
            message="Connected to Windows Event Listener",
            data={"address": str(client_addr)}
        )
        await websocket.send(event.to_json())
        
        try:
            async for message in websocket:
                # Handle incoming messages from client if needed
                self.logger.debug(f"Received from {client_addr}: {message}")
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.clients.remove(websocket)
            self.logger.info(f"Client disconnected: {client_addr}")
    
    async def broadcast(self, event: Any):
        """Broadcast event to all connected clients"""
        if not self.clients:
            return
        
        json_data = event.to_json() if hasattr(event, 'to_json') else json.dumps(event)
        
        # Send to all clients
        disconnected = set()
        for client in self.clients:
            try:
                await client.send(json_data)
            except websockets.exceptions.ConnectionClosed:
                disconnected.add(client)
        
        # Remove disconnected clients
        self.clients -= disconnected


# ==================== Main Event Manager ====================

class WindowsEventManager:
    """Main manager untuk koordinasi semua listeners dan WebSocket"""
    
    def __init__(
        self,
        websocket_host: str = "localhost",
        websocket_port: int = 8765,
        media_interval: float = 2.0,
        message_interval: float = 2.0,
        audio_interval: float = 0.033,  # ~30 FPS untuk smooth animation
        enable_audio: bool = True
    ):
        self.media_listener = MediaPlaybackListener()
        self.message_listener = MessageNotificationListener()
        self.audio_listener = AudioAmplitudeListener() if enable_audio else None
        self.websocket_server = WebSocketEventServer(websocket_host, websocket_port)
        
        self.media_interval = media_interval
        self.message_interval = message_interval
        self.audio_interval = audio_interval
        
        self.is_running = False
        self.logger = logging.getLogger(f"{__name__}.EventManager")
    
    async def start(self):
        """Start all listeners and WebSocket server"""
        self.is_running = True
        
        # Start WebSocket server
        # await self.websocket_server.start()
        
        # Start all listeners
        await self.media_listener.start()
        await self.message_listener.start()
        
        if self.audio_listener:
            await self.audio_listener.start()
        
        self.logger.info("All systems started")
        
        # Start monitoring tasks
        tasks = [
            self._monitor_media(),
            self._monitor_messages(),
        ]
        
        if self.audio_listener:
            tasks.append(self._monitor_audio())
        
        await asyncio.gather(*tasks)
    
    async def stop(self):
        """Stop all listeners and server"""
        self.is_running = False
        
        await self.media_listener.stop()
        await self.message_listener.stop()
        
        if self.audio_listener:
            await self.audio_listener.stop()
        
        # await self.websocket_server.stop()
        
        self.logger.info("All systems stopped")
    
    async def _monitor_media(self):
        """Monitor media playback events"""
        while self.is_running:
            try:
                events = await self.media_listener.get_events()
                for event in events:
                    self.logger.info(f"Media event: {event.title} - {event.status}")
                    # await self.websocket_server.broadcast(event)
            except Exception as e:
                self.logger.error(f"Error in media monitor: {e}")
            
            await asyncio.sleep(self.media_interval)
    
    async def _monitor_messages(self):
        """Monitor message notification events"""
        while self.is_running:
            try:
                events = await self.message_listener.get_events()
                for event in events:
                    self.logger.info(f"Message event: {event.app} - {event.title}")
                    # await self.websocket_server.broadcast(event)
            except Exception as e:
                self.logger.error(f"Error in message monitor: {e}")
            
            await asyncio.sleep(self.message_interval)
    
    async def _monitor_audio(self):
        """Monitor audio amplitude"""
        while self.is_running:
            try:
                events = await self.audio_listener.get_events()
                for event in events:
                    # Only broadcast if amplitude is significant
                    if event.amplitude > 0.01:
                        """"""
                        # await self.websocket_server.broadcast(event)
            except Exception as e:
                self.logger.error(f"Error in audio monitor: {e}")
            
            await asyncio.sleep(self.audio_interval)


# ==================== Main Entry Point ====================

async def main():
    """Main entry point"""
    print("=" * 70)
    print("🎧 WINDOWS 11 EVENT LISTENER - WebSocket Server")
    print("=" * 70)
    print()
    print("📡 WebSocket Server: ws://localhost:8765")
    print()
    print("📤 Events yang dikirim:")
    print("  • media          - Media playback events")
    print("  • message        - Message notifications")
    print("  • audio_amplitude - Audio amplitude data")
    print("  • system         - System events")
    print()
    print("⚙️  Setup untuk Audio Amplitude:")
    print("  1. Aktifkan 'Stereo Mix' di Sound settings")
    print("  2. Atau install VB-Cable (Virtual Audio Cable)")
    print()
    print("📝 Connect dari Electron app:")
    print("  const ws = new WebSocket('ws://localhost:8765');")
    print()
    print("=" * 70)
    print()
    
    # Configuration
    enable_audio = AUDIO_AVAILABLE
    if not enable_audio:
        print("⚠️  Audio amplitude disabled (install: pip install pyaudio numpy)")
        print()
    
    # Create and start event manager
    manager = WindowsEventManager(
        websocket_host="localhost",
        websocket_port=8765,
        media_interval=2.0,
        message_interval=2.0,
        audio_interval=0.033,  # ~30 FPS
        enable_audio=enable_audio
    )
    
    try:
        print("🚀 Starting event listener...")
        print("Press Ctrl+C to stop\n")
        await manager.start()
    except KeyboardInterrupt:
        print("\n\n👋 Shutting down...")
        await manager.stop()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        await manager.stop()


if __name__ == "__main__":
    asyncio.run(main())
"""
Windows Media Controller Library
---------------------------------
Library untuk monitoring dan kontrol media playback di Windows
dengan event-based system untuk deteksi play, pause, dan perubahan media.
"""

import asyncio
import logging
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass
from enum import Enum

from winsdk.windows.media.control import \
    GlobalSystemMediaTransportControlsSessionManager as MediaManager

# Setup logging
logger = logging.getLogger(__name__)


class MediaStatus(Enum):
    """Enum untuk status media playback"""
    CLOSED = 0
    OPENED = 1
    CHANGING = 2
    STOPPED = 3
    PLAYING = 4
    PAUSED = 5
    UNKNOWN = -1


class MediaEvent(Enum):
    """Enum untuk tipe event media"""
    PLAY = "play"
    PAUSE = "pause"
    STOP = "stop"
    MEDIA_CHANGED = "media_changed"
    SESSION_CHANGED = "session_changed"
    STATUS_CHANGED = "status_changed"


@dataclass
class MediaInfo:
    """Data class untuk informasi media"""
    title: str = "Unknown"
    artist: str = "Unknown"
    album: str = "Unknown"
    status: MediaStatus = MediaStatus.UNKNOWN
    is_playing: bool = False
    session_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert ke dictionary"""
        return {
            "title": self.title,
            "artist": self.artist,
            "album": self.album,
            "status": self.status.name,
            "is_playing": self.is_playing
        }
    
    def is_same_media(self, other: 'MediaInfo') -> bool:
        """Check apakah media yang sama (title + artist)"""
        if not isinstance(other, MediaInfo):
            return False
        return (
            self.title == other.title and
            self.artist == other.artist
        )
    
    def is_same_session(self, other: 'MediaInfo') -> bool:
        """Check apakah session yang sama"""
        if not isinstance(other, MediaInfo):
            return False
        return self.session_id == other.session_id


class WindowsMediaController:
    """
    Controller untuk Windows Media dengan event-based system
    
    Usage:
        controller = WindowsMediaController(poll_interval=0.2)
        
        # Register event handlers
        controller.on_play(lambda info: print(f"Playing: {info.title}"))
        controller.on_pause(lambda info: print(f"Paused: {info.title}"))
        controller.on_media_changed(lambda old, new: print(f"Changed: {old.title} -> {new.title}"))
        
        # Start monitoring
        await controller.start()
        
        # Get current media info
        info = controller.get_current_media()
        
        # Stop monitoring
        await controller.stop()
    """
    
    def __init__(self, poll_interval: float = 0.2):
        """
        Initialize controller
        
        Args:
            poll_interval: Interval polling dalam detik (default: 0.2)
        """
        self.poll_interval = poll_interval
        self.is_running = False
        
        # Current state
        self._current_media = MediaInfo()
        self._last_triggered_media = MediaInfo()  # Track last media yang di-trigger event
        
        # Event handlers
        self._event_handlers: Dict[MediaEvent, list] = {
            MediaEvent.PLAY: [],
            MediaEvent.PAUSE: [],
            MediaEvent.STOP: [],
            MediaEvent.MEDIA_CHANGED: [],
            MediaEvent.SESSION_CHANGED: [],
            MediaEvent.STATUS_CHANGED: []
        }
        
        # Background task
        self._poller_task: Optional[asyncio.Task] = None
        
        # First run flag
        self._first_run = True
    
    # ==================== Event Registration ====================
    
    def on_play(self, callback: Callable[[MediaInfo], None]):
        """Register callback untuk event play"""
        self._event_handlers[MediaEvent.PLAY].append(callback)
        return self
    
    def on_pause(self, callback: Callable[[MediaInfo], None]):
        """Register callback untuk event pause"""
        self._event_handlers[MediaEvent.PAUSE].append(callback)
        return self
    
    def on_stop(self, callback: Callable[[MediaInfo], None]):
        """Register callback untuk event stop"""
        self._event_handlers[MediaEvent.STOP].append(callback)
        return self
    
    def on_media_changed(self, callback: Callable[[MediaInfo, MediaInfo], None]):
        """
        Register callback untuk event media berubah
        Callback menerima (old_media, new_media)
        """
        self._event_handlers[MediaEvent.MEDIA_CHANGED].append(callback)
        return self
    
    def on_session_changed(self, callback: Callable[[MediaInfo], None]):
        """Register callback untuk event aplikasi media berubah"""
        self._event_handlers[MediaEvent.SESSION_CHANGED].append(callback)
        return self
    
    def on_status_changed(self, callback: Callable[[MediaStatus, MediaStatus, MediaInfo], None]):
        """
        Register callback untuk event status berubah
        Callback menerima (old_status, new_status, media_info)
        """
        self._event_handlers[MediaEvent.STATUS_CHANGED].append(callback)
        return self
    
    # ==================== Lifecycle ====================
    
    async def start(self):
        """Start monitoring media"""
        if self.is_running:
            logger.warning("Media controller already running")
            return
        
        self.is_running = True
        self._first_run = True
        self._poller_task = asyncio.create_task(self._background_poller())
    
    async def stop(self):
        """Stop monitoring media"""
        if not self.is_running:
            return
        
        self.is_running = False
        
        if self._poller_task:
            self._poller_task.cancel()
            try:
                await self._poller_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Windows Media Controller stopped")
    
    # ==================== Public Methods ====================
    
    def get_current_media(self) -> MediaInfo:
        """Get informasi media saat ini (instant, dari cache)"""
        return self._current_media
    
    def is_media_playing(self) -> bool:
        """Check apakah ada media yang sedang playing"""
        return self._current_media.is_playing
    
    # ==================== Internal Methods ====================
    
    async def _background_poller(self):
        """Background task untuk polling media info"""
        logger.info("Media poller started")
        
        while self.is_running:
            try:
                await self._poll_and_detect_changes()
            except Exception as e:
                logger.error(f"Poller error: {e}", exc_info=True)
            
            await asyncio.sleep(self.poll_interval)
        
        logger.info("Media poller stopped")
    
    async def _poll_and_detect_changes(self):
        """Poll media info dan deteksi perubahan"""
        try:
            # Get current session
            sessions = await MediaManager.request_async()
            current_session = sessions.get_current_session()
            
            # No active session
            if not current_session:
                await self._handle_no_session()
                return
            
            # Get unique session ID
            session_id = str(id(current_session))
            
            # Get media properties
            info = await current_session.try_get_media_properties_async()
            playback_info = current_session.get_playback_info()
            
            # Parse status
            status = MediaStatus(playback_info.playback_status) if playback_info.playback_status in range(6) else MediaStatus.UNKNOWN
            is_playing = (status == MediaStatus.PLAYING)
            
            # Create new media info
            new_media = MediaInfo(
                title=info.title or "Unknown",
                artist=info.artist or "Unknown",
                album=info.album_title or "Unknown",
                status=status,
                is_playing=is_playing,
                session_id=session_id
            )
            
            # Detect changes and trigger events
            await self._detect_and_trigger_events(new_media)
            
            # Update current media
            self._current_media = new_media
            
            # Mark first run as done
            if self._first_run:
                self._first_run = False
            
        except Exception as e:
            logger.error(f"Error polling media: {e}", exc_info=True)
    
    async def _handle_no_session(self):
        """Handle ketika tidak ada session aktif"""
        # Jika sebelumnya ada media, trigger stop event
        if self._current_media.title != "Unknown" and not self._first_run:
            await self._trigger_event(MediaEvent.STOP, self._current_media)
        
        # Reset to unknown
        self._current_media = MediaInfo()
        self._last_triggered_media = MediaInfo()
    
    async def _detect_and_trigger_events(self, new_media: MediaInfo):
        """Deteksi perubahan dan trigger events yang sesuai"""
        old_media = self._current_media
        last_triggered = self._last_triggered_media
        
        # Skip events on first run (initial state)
        if self._first_run:
            self._last_triggered_media = new_media
            return
        
        # 1. SESSION CHANGED - hanya trigger jika session_id berbeda
        if not new_media.is_same_session(old_media):
            await self._trigger_event(MediaEvent.SESSION_CHANGED, new_media)
            self._last_triggered_media = new_media
        
        # 2. MEDIA CHANGED - hanya trigger jika title/artist berbeda dari last triggered
        elif not new_media.is_same_media(last_triggered):
            await self._trigger_event(MediaEvent.MEDIA_CHANGED, old_media, new_media)
            self._last_triggered_media = new_media
        
        # 3. STATUS CHANGED - trigger jika status berubah
        if new_media.status != old_media.status:
            await self._trigger_event(MediaEvent.STATUS_CHANGED, old_media.status, new_media.status, new_media)
            
            # 4. PLAY/PAUSE/STOP events - berdasarkan perubahan status
            if new_media.status == MediaStatus.PLAYING and old_media.status != MediaStatus.PLAYING:
                await self._trigger_event(MediaEvent.PLAY, new_media)
            
            elif new_media.status == MediaStatus.PAUSED and old_media.status == MediaStatus.PLAYING:
                await self._trigger_event(MediaEvent.PAUSE, new_media)
            
            elif new_media.status == MediaStatus.STOPPED and old_media.status != MediaStatus.STOPPED:
                await self._trigger_event(MediaEvent.STOP, new_media)
    
    async def _trigger_event(self, event: MediaEvent, *args):
        """Trigger event handlers"""
        handlers = self._event_handlers.get(event, [])
        
        for handler in handlers:
            try:
                # Support both sync and async handlers
                if asyncio.iscoroutinefunction(handler):
                    await handler(*args)
                else:
                    handler(*args)
            except Exception as e:
                logger.error(f"Error in event handler for {event.value}: {e}", exc_info=True)

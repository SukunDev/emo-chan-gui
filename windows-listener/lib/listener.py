import json
from dataclasses import dataclass, asdict
import logging
import asyncio
import time

# Media Control
from winsdk.windows.media.control import \
    GlobalSystemMediaTransportControlsSessionManager as MediaManager

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
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ==================== Data Models ====================

@dataclass
class MediaAudioEvent:
    """Model untuk combined media + audio event (minimal data)"""
    type: str = "media"
    title: str = ""
    artist: str = ""
    status: str = ""
    is_playing: bool = False
    audio_amplitude: dict = None
    
    def __post_init__(self):
        if self.audio_amplitude is None:
            self.audio_amplitude = {"amplitude": 0.0, "peak": 0.0, "rms": 0.0}
    
    def to_json(self) -> str:
        return json.dumps(asdict(self), separators=(',', ':'))  # Compact JSON


# ==================== Media Listener ====================

class MediaPlaybackListener:
    """Listener untuk media playback dengan intelligent caching"""
    
    def __init__(self):
        self.is_running = False
        
        # Cache data
        self._cached_title = "Unknown"
        self._cached_artist = "Unknown"
        self._cached_status = "Unknown"
        self._cached_is_playing = False
        self._cache_valid = False
        
        # Background polling
        self._poller_task = None
        self._poll_interval = 0.2  # Poll setiap 200ms
        
        # Session tracking untuk detect changes
        self._last_session_id = None
    
    async def start(self):
        """Start media listener dengan background polling"""
        self.is_running = True
        
        # Start background poller
        self._poller_task = asyncio.create_task(self._background_poller())
        
        logger.info("Media listener started with background polling")
    
    async def stop(self):
        """Stop media listener"""
        self.is_running = False
        
        if self._poller_task:
            self._poller_task.cancel()
            try:
                await self._poller_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Media listener stopped")
    
    async def _background_poller(self):
        """Background task yang polling media info"""
        logger.info("Background media poller started")
        
        while self.is_running:
            try:
                await self._fetch_and_update_cache()
            except Exception as e:
                logger.error(f"Poller error: {e}")
            
            await asyncio.sleep(self._poll_interval)
        
        logger.info("Background media poller stopped")
    
    async def _fetch_and_update_cache(self):
        """Fetch media info dan update cache jika ada perubahan"""
        try:
            sessions = await MediaManager.request_async()
            current_session = sessions.get_current_session()
            
            # Tidak ada session aktif
            if not current_session:
                # Update cache ke "Unknown" jika session hilang
                if self._cached_title != "Unknown":
                    self._cached_title = "Unknown"
                    self._cached_artist = "Unknown"
                    self._cached_status = "Unknown"
                    self._cached_is_playing = False
                    self._cache_valid = True
                    logger.info("No active media session")
                return
            
            # Check if session changed (detect app change)
            session_id = id(current_session)
            session_changed = (session_id != self._last_session_id)
            self._last_session_id = session_id
            
            # Get media info
            info = await current_session.try_get_media_properties_async()
            playback_info = current_session.get_playback_info()
            
            status_map = {
                0: 'Closed', 1: 'Opened', 2: 'Changing',
                3: 'Stopped', 4: 'Playing', 5: 'Paused'
            }
            
            status = status_map.get(playback_info.playback_status, 'Unknown')
            is_playing = (playback_info.playback_status == 4)
            
            title = info.title or "Unknown"
            artist = info.artist or "Unknown"
            
            # Check if data berubah
            data_changed = (
                title != self._cached_title or
                artist != self._cached_artist or
                status != self._cached_status or
                is_playing != self._cached_is_playing or
                session_changed
            )
            
            if data_changed:
                self._cached_title = title
                self._cached_artist = artist
                self._cached_status = status
                self._cached_is_playing = is_playing
                self._cache_valid = True
                
                logger.debug(f"Media updated: {title} by {artist} - {status}")
            
        except Exception as e:
            logger.error(f"Error fetching media: {e}")
            # Jangan ubah cache jika ada error, biar tetap konsisten
    
    async def get_current_media(self) -> tuple:
        """
        Get current media info dari cache - INSTANT!
        Returns: (title, artist, status, is_playing)
        """
        if not self.is_running:
            return ("Unknown", "Unknown", "Unknown", False)
        
        # Tunggu sebentar jika cache belum valid (first run)
        if not self._cache_valid:
            # Tunggu max 500ms untuk initial fetch
            for _ in range(5):
                if self._cache_valid:
                    break
                await asyncio.sleep(0.1)
        
        # Return cached data - NO BLOCKING!
        return (
            self._cached_title,
            self._cached_artist,
            self._cached_status,
            self._cached_is_playing
        )


# ==================== Audio Amplitude Listener ====================

class AudioAmplitudeListener:
    """Listener untuk audio amplitude"""
    
    def __init__(self, chunk_size: int = 1024, sample_rate: int = 44100):
        self.chunk_size = chunk_size
        self.sample_rate = sample_rate
        self.audio_data = np.zeros(chunk_size) if AUDIO_AVAILABLE else None
        self.pyaudio_instance = None
        self.stream = None
        self.is_running = False
        self.available = AUDIO_AVAILABLE
    
    async def start(self):
        """Start audio capture"""
        if not self.available:
            logger.warning("Audio capture not available")
            return
        
        self.is_running = True
        
        try:
            self.pyaudio_instance = pyaudio.PyAudio()
            device_index = self._find_loopback_device()
            
            if device_index is None:
                logger.error("No loopback device found. Enable 'Stereo Mix' or install VB-Cable")
                self.is_running = False
                return
            
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
            logger.info(f"Audio capture started (device: {device_index})")
            
        except Exception as e:
            logger.error(f"Failed to start audio capture: {e}")
            self.is_running = False
    
    async def stop(self):
        """Stop audio capture"""
        self.is_running = False
        
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        
        if self.pyaudio_instance:
            self.pyaudio_instance.terminate()
        
        logger.info("Audio capture stopped")
    
    def get_current_amplitude(self) -> dict:
        """Get current audio amplitude metrics"""
        if not self.is_running or self.audio_data is None:
            return {"amplitude": 0.0, "peak": 0.0, "rms": 0.0}
        
        try:
            audio_abs = np.abs(self.audio_data)
            
            amplitude = float(audio_abs.mean()) / 32768.0 if len(audio_abs) > 0 else 0.0
            peak = float(audio_abs.max()) / 32768.0 if len(audio_abs) > 0 else 0.0
            
            if len(self.audio_data) > 0:
                audio_squared = self.audio_data.astype(np.float64) ** 2
                mean_squared = np.mean(audio_squared)
                rms = float(np.sqrt(mean_squared)) / 32768.0 if mean_squared >= 0 else 0.0
            else:
                rms = 0.0
            
            # Round to 2 decimals untuk menghemat bandwidth
            return {
                "amplitude": round(amplitude, 2),
                "peak": round(peak, 2),
                "rms": round(rms, 2)
            }
            
        except Exception as e:
            logger.error(f"Error calculating amplitude: {e}")
            return {"amplitude": 0.0, "peak": 0.0, "rms": 0.0}
    
    def _audio_callback(self, in_data, frame_count, time_info, status):
        """Callback for audio data"""
        if self.is_running:
            self.audio_data = np.frombuffer(in_data, dtype=np.int16)
        return (in_data, pyaudio.paContinue)
    
    def _find_loopback_device(self):
        """Find loopback device for system audio"""
        for i in range(self.pyaudio_instance.get_device_count()):
            dev_info = self.pyaudio_instance.get_device_info_by_index(i)
            name = dev_info.get('name', '').lower()
            if any(keyword in name for keyword in ['stereo mix', 'loopback', 'what u hear']):
                if dev_info.get('maxInputChannels', 0) > 0:
                    return i
        return None
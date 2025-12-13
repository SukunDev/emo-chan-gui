
import json
from dataclasses import dataclass, asdict
import logging

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
    """Listener untuk media playback"""
    
    def __init__(self):
        self.is_running = False
        self.last_media_state = None
    
    async def start(self):
        self.is_running = True
        logger.info("Media listener started")
    
    async def stop(self):
        self.is_running = False
        logger.info("Media listener stopped")
    
    async def get_current_media(self) -> tuple:
        """Get current media info: (title, artist, status, is_playing)"""
        if not self.is_running:
            return ("Unknown", "Unknown", "Unknown", False)
        
        try:
            sessions = await MediaManager.request_async()
            current_session = sessions.get_current_session()
            
            # 🔥 PERBAIKAN: Return None jika tidak ada session
            if not current_session:
                return (None, None, None, None)  # Beda dengan "Unknown"
            
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
            
            return (title, artist, status, is_playing)
            
        except Exception as e:
            logger.error(f"Error getting media info: {e}")
            return ("Unknown", "Unknown", "Unknown", False)


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

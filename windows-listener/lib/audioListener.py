"""
Audio Listener Library
----------------------
Library untuk capture dan monitoring audio amplitude dari system audio
dengan support untuk loopback device (Stereo Mix / VB-Cable).
"""

import asyncio
import logging
import threading
from typing import Optional, Callable, Dict
from dataclasses import dataclass

try:
    import pyaudio
    import numpy as np
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False
    pyaudio = None
    np = None

# Setup logging
logger = logging.getLogger(__name__)


@dataclass
class AudioMetrics:
    """Data class untuk audio metrics"""
    amplitude: float = 0.0  # Mean amplitude (0.0 - 1.0)
    peak: float = 0.0       # Peak amplitude (0.0 - 1.0)
    rms: float = 0.0        # RMS (Root Mean Square) (0.0 - 1.0)
    
    def to_dict(self) -> Dict[str, float]:
        """Convert ke dictionary"""
        return {
            "amplitude": round(self.amplitude, 3),
            "peak": round(self.peak, 3),
            "rms": round(self.rms, 3)
        }
    
    def is_silent(self, threshold: float = 0.01) -> bool:
        """Check apakah audio silent berdasarkan threshold"""
        return self.rms < threshold


class AudioListener:
    """
    Audio listener untuk capture system audio dan calculate amplitude metrics
    
    Usage:
        listener = AudioListener(chunk_size=1024, sample_rate=44100)
        
        # Check availability
        if not listener.is_available():
            print("Audio capture not available!")
            return
        
        # Register callback untuk audio metrics
        listener.on_audio_data(lambda metrics: print(f"RMS: {metrics.rms:.3f}"))
        
        # Start listening
        await listener.start()
        
        # Get current metrics
        metrics = listener.get_metrics()
        
        # Stop listening
        await listener.stop()
    """
    
    def __init__(
        self,
        chunk_size: int = 1024,
        sample_rate: int = 44100,
        auto_detect_device: bool = True,
        device_index: Optional[int] = None
    ):
        """
        Initialize audio listener
        
        Args:
            chunk_size: Ukuran buffer audio (default: 1024)
            sample_rate: Sample rate dalam Hz (default: 44100)
            auto_detect_device: Auto-detect loopback device (default: True)
            device_index: Manual device index (opsional)
        """
        self.chunk_size = chunk_size
        self.sample_rate = sample_rate
        self.auto_detect_device = auto_detect_device
        self.manual_device_index = device_index
        
        # State
        self.is_running = False
        self.available = AUDIO_AVAILABLE
        
        # PyAudio objects
        self.pyaudio_instance = None
        self.stream = None
        
        # Audio data buffer
        self.audio_buffer = np.zeros(chunk_size) if AUDIO_AVAILABLE else None
        self.current_metrics = AudioMetrics()
        
        # Callbacks - use thread-safe list
        self._audio_callbacks = []
        self._callbacks_lock = threading.Lock()
        
        # Event loop reference
        self._loop = None
        
        if not AUDIO_AVAILABLE:
            logger.warning("PyAudio/NumPy not available. Install with: pip install pyaudio numpy")
    
    # ==================== Public Methods ====================
    
    def is_available(self) -> bool:
        """Check apakah audio capture tersedia"""
        return self.available
    
    def on_audio_data(self, callback: Callable[[AudioMetrics], None]):
        """
        Register callback untuk audio data
        Callback dipanggil setiap kali ada audio data baru
        """
        with self._callbacks_lock:
            self._audio_callbacks.append(callback)
        return self
    
    async def start(self) -> bool:
        """
        Start audio capture
        
        Returns:
            True jika berhasil start, False jika gagal
        """
        if not self.available:
            logger.error("Audio capture not available")
            return False
        
        if self.is_running:
            logger.warning("Audio listener already running")
            return True
        
        try:
            # Store event loop reference
            self._loop = asyncio.get_running_loop()
            
            self.pyaudio_instance = pyaudio.PyAudio()
            
            # Detect atau gunakan device index manual
            if self.manual_device_index is not None:
                device_index = self.manual_device_index
            elif self.auto_detect_device:
                device_index = self._find_loopback_device()
            else:
                device_index = None
            
            if device_index is None:
                logger.error(
                    "No loopback device found. "
                    "Please enable 'Stereo Mix' in Windows Sound Settings "
                    "or install VB-Cable virtual audio device."
                )
                return False
            
            # Open audio stream
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
            self.is_running = True
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to start audio listener: {e}", exc_info=True)
            await self._cleanup()
            return False
    
    async def stop(self):
        """Stop audio capture"""
        if not self.is_running:
            return
        
        self.is_running = False
        await self._cleanup()
    
    def get_metrics(self) -> AudioMetrics:
        """Get current audio metrics (instant, dari buffer)"""
        return self.current_metrics
    
    def list_devices(self) -> list:
        """
        List semua audio devices yang tersedia
        
        Returns:
            List of dict dengan info device
        """
        if not self.available:
            return []
        
        devices = []
        p = pyaudio.PyAudio()
        
        try:
            for i in range(p.get_device_count()):
                info = p.get_device_info_by_index(i)
                devices.append({
                    'index': i,
                    'name': info.get('name', ''),
                    'max_input_channels': info.get('maxInputChannels', 0),
                    'max_output_channels': info.get('maxOutputChannels', 0),
                    'default_sample_rate': info.get('defaultSampleRate', 0)
                })
        finally:
            p.terminate()
        
        return devices
    
    def find_loopback_devices(self) -> list:
        """
        Cari semua loopback devices yang tersedia
        
        Returns:
            List of dict dengan info loopback device
        """
        if not self.available:
            return []
        
        loopback_devices = []
        p = pyaudio.PyAudio()
        
        try:
            for i in range(p.get_device_count()):
                info = p.get_device_info_by_index(i)
                name = info.get('name', '').lower()
                
                # Check keywords untuk loopback device
                keywords = ['stereo mix', 'loopback', 'what u hear', 'wave out mix', 'vb-cable']
                if any(keyword in name for keyword in keywords):
                    if info.get('maxInputChannels', 0) > 0:
                        loopback_devices.append({
                            'index': i,
                            'name': info.get('name', ''),
                            'channels': info.get('maxInputChannels', 0)
                        })
        finally:
            p.terminate()
        
        return loopback_devices
    
    # ==================== Internal Methods ====================
    
    def _audio_callback(self, in_data, frame_count, time_info, status):
        """Callback untuk audio stream (dipanggil dari thread PyAudio)"""
        if not self.is_running:
            return (in_data, pyaudio.paComplete)
        
        try:
            # Convert audio data ke numpy array
            self.audio_buffer = np.frombuffer(in_data, dtype=np.int16)
            
            # Calculate metrics
            self.current_metrics = self._calculate_metrics(self.audio_buffer)
            
            # Trigger callbacks (thread-safe, non-blocking)
            self._trigger_callbacks_sync(self.current_metrics)
            
        except Exception as e:
            logger.error(f"Error in audio callback: {e}")
        
        return (in_data, pyaudio.paContinue)
    
    def _calculate_metrics(self, audio_data: np.ndarray) -> AudioMetrics:
        """Calculate audio metrics dari audio data"""
        try:
            if len(audio_data) == 0:
                return AudioMetrics()
            
            # Normalize to float (0.0 - 1.0)
            audio_abs = np.abs(audio_data)
            max_int16 = 32768.0
            
            # Mean amplitude
            amplitude = float(audio_abs.mean()) / max_int16
            
            # Peak amplitude
            peak = float(audio_abs.max()) / max_int16
            
            # RMS (Root Mean Square)
            audio_float = audio_data.astype(np.float64)
            rms_value = np.sqrt(np.mean(audio_float ** 2)) / max_int16
            rms = float(rms_value)
            
            return AudioMetrics(
                amplitude=amplitude,
                peak=peak,
                rms=rms
            )
            
        except Exception as e:
            logger.error(f"Error calculating metrics: {e}")
            return AudioMetrics()
    
    def _trigger_callbacks_sync(self, metrics: AudioMetrics):
        """
        Trigger callbacks secara synchronous (thread-safe)
        Dipanggil dari PyAudio callback thread
        """
        with self._callbacks_lock:
            callbacks = self._audio_callbacks.copy()
        
        for callback in callbacks:
            try:
                # Check if callback is async
                if asyncio.iscoroutinefunction(callback):
                    # Schedule coroutine in event loop (thread-safe)
                    if self._loop and not self._loop.is_closed():
                        self._loop.call_soon_threadsafe(
                            lambda: asyncio.create_task(callback(metrics))
                        )
                else:
                    # Call sync callback directly
                    callback(metrics)
            except Exception as e:
                logger.error(f"Error in audio callback: {e}")
    
    def _find_loopback_device(self) -> Optional[int]:
        """Auto-detect loopback device"""
        if not self.pyaudio_instance:
            return None
        
        for i in range(self.pyaudio_instance.get_device_count()):
            info = self.pyaudio_instance.get_device_info_by_index(i)
            name = info.get('name', '').lower()
            
            # Check keywords
            keywords = ['stereo mix', 'loopback', 'what u hear', 'wave out mix', 'vb-cable']
            if any(keyword in name for keyword in keywords):
                if info.get('maxInputChannels', 0) > 0:
                    return i
        
        return None
    
    def _get_device_name(self, device_index: int) -> str:
        """Get device name dari index"""
        if not self.pyaudio_instance:
            return "Unknown"
        
        try:
            info = self.pyaudio_instance.get_device_info_by_index(device_index)
            return info.get('name', f'Device {device_index}')
        except:
            return f'Device {device_index}'
    
    async def _cleanup(self):
        """Cleanup PyAudio resources"""
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except:
                pass
            self.stream = None
        
        if self.pyaudio_instance:
            try:
                self.pyaudio_instance.terminate()
            except:
                pass
            self.pyaudio_instance = None
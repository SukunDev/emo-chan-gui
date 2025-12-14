"""
Media Audio Monitor
-------------------
Unified class untuk monitoring media playback dan audio amplitude
dengan JSON output format.
"""

import asyncio
import json
from typing import Optional, Callable
from lib import WindowsMediaController, AudioListener


class MediaAudioMonitor:
    """
    Unified monitor untuk media playback dan audio amplitude
    
    Usage:
        monitor = MediaAudioMonitor()
        
        # Get realtime JSON data
        json_data = monitor.get_json()
        
        # Register callback untuk realtime updates
        monitor.on_update(lambda data: print(data))
        
        # Start monitoring
        await monitor.start()
        
        # Stop monitoring
        await monitor.stop()
    """
    
    def __init__(self):
        # Controllers
        self._media_controller = WindowsMediaController(poll_interval=0.2)
        self._audio_listener = AudioListener(chunk_size=1024, sample_rate=44100)
        
        # Current state
        self._current_data = {
            "type": "media",
            "title": "Unknown",
            "artist": "Unknown",
            "status": "Unknown",
            "is_playing": False,
            "audio_amplitude": {
                "amplitude": 0.0,
                "peak": 0.0,
                "rms": 0.0
            }
        }
        
        # Update callbacks
        self._update_callbacks = []
        
        # Running state
        self.is_running = False
    
    # ==================== Public Methods ====================
    
    async def start(self) -> bool:
        """
        Start monitoring media dan audio
        
        Returns:
            True jika berhasil start
        """
        if self.is_running:
            return True
        
        # Setup media controller
        self._media_controller.on_play(lambda info: self._on_media_update(info))
        self._media_controller.on_pause(lambda info: self._on_media_update(info))
        self._media_controller.on_media_changed(lambda old, new: self._on_media_update(new))
        self._media_controller.on_status_changed(lambda old, new, info: self._on_media_update(info))
        
        # Start media controller
        await self._media_controller.start()
        
        # Setup audio listener
        if self._audio_listener.is_available():
            self._audio_listener.on_audio_data(lambda metrics: self._on_audio_update(metrics))
            await self._audio_listener.start()
        
        self.is_running = True
        return True
    
    async def stop(self):
        """Stop monitoring"""
        if not self.is_running:
            return
        
        await self._media_controller.stop()
        
        if self._audio_listener.is_running:
            await self._audio_listener.stop()
        
        self.is_running = False
    
    def get_json(self) -> str:
        """
        Get current data sebagai JSON string
        
        Returns:
            JSON string dengan format compact
        """
        return json.dumps(self._current_data, separators=(',', ':'))
    
    def get_data(self) -> dict:
        """
        Get current data sebagai dictionary
        
        Returns:
            Dictionary dengan current data
        """
        return self._current_data.copy()
    
    def on_update(self, callback: Callable[[str], None]):
        """
        Register callback untuk realtime updates
        Callback menerima JSON string setiap ada perubahan
        
        Args:
            callback: Function yang menerima JSON string
        """
        self._update_callbacks.append(callback)
        return self
    
    def get_audio_devices(self) -> list:
        """Get list loopback devices yang tersedia"""
        return self._audio_listener.find_loopback_devices()
    
    # ==================== Internal Methods ====================
    
    def _on_media_update(self, info):
        """Handler untuk media update"""
        self._current_data["title"] = info.title
        self._current_data["artist"] = info.artist
        self._current_data["status"] = info.status.name
        self._current_data["is_playing"] = info.is_playing
        
        # Trigger callbacks
        self._trigger_updates()
    
    def _on_audio_update(self, metrics):
        """Handler untuk audio update"""
        self._current_data["audio_amplitude"] = {
            "amplitude": round(metrics.amplitude, 2),
            "peak": round(metrics.peak, 2),
            "rms": round(metrics.rms, 2)
        }
        
        # Trigger callbacks (limit frequency untuk audio)
        # Only trigger if significant change to avoid spam
        if self._should_trigger_audio_update(metrics):
            self._trigger_updates()
    
    def _should_trigger_audio_update(self, metrics) -> bool:
        """Check apakah perlu trigger update untuk audio"""
        # Trigger setiap 0.1s (reduce callback frequency)
        # Atau jika ada perubahan signifikan
        current_rms = self._current_data["audio_amplitude"]["rms"]
        return abs(metrics.rms - current_rms) > 0.05  # 5% threshold
    
    def _trigger_updates(self):
        """Trigger all registered callbacks"""
        json_data = self.get_json()
        
        for callback in self._update_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    asyncio.create_task(callback(json_data))
                else:
                    callback(json_data)
            except Exception:
                pass  # Silent fail untuk callbacks
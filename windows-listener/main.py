from lib import MediaAudioMonitor, NotificationMonitor, Server
import asyncio
import signal
import os
import sys
import tempfile
import traceback
import json


LOCK_FILE = os.path.join(
    tempfile.gettempdir(),
    "esp32_pet_backend.lock"
)

def acquire_lock():
    """Prevent backend from running multiple times"""
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, "r") as f:
                pid = int(f.read().strip())

            os.kill(pid, 0)
            print("[INFO] Backend already running, exit.")
            sys.exit(0)

        except Exception:
            try:
                os.remove(LOCK_FILE)
            except Exception:
                pass

    try:
        with open(LOCK_FILE, "w") as f:
            f.write(str(os.getpid()))
    except Exception:
        sys.exit(1)


def release_lock():
    try:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
    except Exception:
        pass


media_monitor = None
notif_monitor = None
server = None
shutdown_event = asyncio.Event()
server_task = None

# Track last media state untuk avoid spam
last_media_data = None
AMPLITUDE_THRESHOLD = 0.01  # Minimum amplitude untuk dianggap "ada audio"


def on_notification_received(notif):
    if not shutdown_event.is_set():
        timestamp = notif.time
        app_name = notif.app_name
        if server:
            notification_json = {
                "type": "notification",
                "app": app_name,
                "time": timestamp,
                "texts": notif.texts
            }
            Server.publish(json.dumps(notification_json))


def should_send_media(new_data):
    """
    Tentukan apakah media data perlu dikirim.
    Hanya kirim jika:
    1. Ada audio aktif (amplitude > threshold), ATAU
    2. Status berubah (playing/paused/stopped)
    """
    global last_media_data
    
    try:
        new_dict = json.loads(new_data) if isinstance(new_data, str) else new_data
        
        # Cek amplitude
        amplitude = new_dict.get("audio_amplitude", {}).get("amplitude", 0.0)
        is_playing = new_dict.get("is_playing", False)
        
        # Jika ada audio aktif, selalu kirim
        if amplitude > AMPLITUDE_THRESHOLD:
            last_media_data = new_dict
            return True
        
        # Jika tidak ada last_media_data, kirim sekali
        if last_media_data is None:
            last_media_data = new_dict
            return False  # Tidak perlu kirim data kosong pertama kali
        
        # Cek apakah ada perubahan status penting
        old_playing = last_media_data.get("is_playing", False)
        old_title = last_media_data.get("title", "")
        new_title = new_dict.get("title", "")
        
        # Kirim jika:
        # - Status playing berubah dari True ke False (berhenti)
        # - Title berubah (lagu baru)
        changed = (
            (old_playing and not is_playing) or  # Baru berhenti
            (old_title != new_title and new_title != "Unknown")  # Lagu baru
        )
        
        if changed:
            last_media_data = new_dict
            return True
        
        # Tidak ada perubahan penting, skip
        return False
        
    except Exception as e:
        print(f"[WARN] Error checking media data: {e}")
        return False


async def main():
    global media_monitor, notif_monitor, server, server_task

    loop = asyncio.get_running_loop()

    server = Server(host="127.0.0.1", port=8765)
    Server.init_loop(loop)

    server_task = asyncio.create_task(server.start())

    media_monitor = MediaAudioMonitor()
    success = await media_monitor.start()

    if not success:
        print("[ERROR] Failed to start MediaAudioMonitor")
        shutdown_event.set()
        return

    notif_monitor = NotificationMonitor(check_interval=1.0)
    notif_monitor.on_notification(on_notification_received)
    
    notif_success = await notif_monitor.start()
    if notif_success:
        print("[INFO] NotificationMonitor started")
    else:
        print("[WARN] NotificationMonitor failed to start (permission may be required)")

    print("[INFO] Backend started")

    try:
        while not shutdown_event.is_set():
            json_data = media_monitor.get_json()
            
            # Hanya kirim jika ada perubahan penting atau audio aktif
            if should_send_media(json_data):
                Server.publish(json_data)
            
            # Kurangi frequency checking - 0.1 detik sudah cukup
            await asyncio.sleep(0.033)

    except asyncio.CancelledError:
        pass
    finally:
        print("[INFO] Shutting down backend")

        if server:
            print("[INFO] Disconnecting BLE")
            await server.disconnect_ble()
            
        if notif_monitor:
            print("[INFO] Shutting down Notif Monitor")
            await notif_monitor.stop()
        
        if media_monitor:
            print("[INFO] Shutting down Media Monitor")
            await media_monitor.stop()
        
        if server_task and not server_task.done():
            print("[INFO] Shutting down Task")
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError as e:
                print(f"[ERROR] {e}")
                pass


def signal_handler(sig, frame):
    """Handle SIGINT/SIGTERM"""
    print("\n[INFO] Received shutdown signal")
    shutdown_event.set()


def setup_signal_handlers():
    """Setup signal handlers untuk graceful shutdown"""
    signal.signal(signal.SIGINT, signal_handler)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, signal_handler)


if __name__ == "__main__":
    acquire_lock()
    setup_signal_handlers()

    try:
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        
        asyncio.run(main())

    except KeyboardInterrupt:
        print("\n[INFO] Keyboard interrupt received")

    except Exception as e:
        print(f"[ERROR] Fatal error: {e}")
        traceback.print_exc()

    finally:
        release_lock()
        print("[INFO] Backend exited")
from lib import MediaAudioMonitor, Server
import asyncio
import signal
import os
import sys
import tempfile
import traceback


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


monitor = None
server = None
shutdown_event = asyncio.Event()
server_task = None


async def main():
    """Main application with MediaAudioMonitor"""
    global monitor, server, server_task

    loop = asyncio.get_running_loop()

    server = Server(host="127.0.0.1", port=8765)
    Server.init_loop(loop)

    # Start server sebagai background task (jangan await langsung!)
    server_task = asyncio.create_task(server.start())

    monitor = MediaAudioMonitor()
    success = await monitor.start()

    if not success:
        print("[ERROR] Failed to start MediaAudioMonitor")
        shutdown_event.set()
        return

    print("[INFO] Backend started")

    try:
        # Main loop - terus jalan sampai shutdown
        while not shutdown_event.is_set():
            json_data = monitor.get_json()
            Server.publish(json_data)
            await asyncio.sleep(0.033)

    except asyncio.CancelledError:
        pass
    finally:
        print("[INFO] Shutting down backend")
        
        # Stop monitor
        await monitor.stop()
        
        # Cancel server task
        if server_task and not server_task.done():
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
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
        # Pastikan ProactorEventLoop untuk main thread
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
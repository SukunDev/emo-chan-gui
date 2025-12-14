from lib import MediaAudioMonitor, Server
import asyncio
import signal


monitor = None
server = None
shutdown_event = asyncio.Event()


async def main():
    """Main application dengan MediaAudioMonitor"""
    global monitor, server

    loop = asyncio.get_running_loop()
    
    server = Server(host="127.0.0.1", port=8765)
    Server.init_loop(loop)

    asyncio.create_task(server.start())

    monitor = MediaAudioMonitor()
    devices = monitor.get_audio_devices()
    if devices:
        print(f"✅ Found {len(devices)} loopback device(s)")
        for dev in devices:
            print(f"   - [{dev['index']}] {dev['name']}")
    else:
        print("⚠️  No loopback device found")
        print("   Enable 'Stereo Mix' in Windows Sound Settings\n")
    
    # Start monitoring
    success = await monitor.start()
    
    if not success:
        print("❌ Failed to start monitoring")
        return
    
    try:
        while not shutdown_event.is_set():
            json_data = monitor.get_json()
            Server.publish(json_data)

            await asyncio.sleep(0.033)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Keyboard interrupt received...")
    
    finally:
        print("\n🛑 Stopping monitor...")
        await monitor.stop()
        print("👋 Monitoring stopped!\n")

# ==================== Signal Handler ====================

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    shutdown_event.set()


def setup_signal_handlers():
    """Setup signal handlers"""
    signal.signal(signal.SIGINT, signal_handler)
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, signal_handler)


# ==================== Run ====================

if __name__ == "__main__":
    setup_signal_handlers()
    try:
        asyncio.run(main())
        
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
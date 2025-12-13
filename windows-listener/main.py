from lib import Server
import asyncio


async def main():
    server = Server(host="127.0.0.1", port=8765)
    await server.start()

asyncio.run(main())
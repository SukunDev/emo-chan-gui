import asyncio
import websockets
import json
from .helper import logging

class WebSocketServer:
    def __init__(self, host="0.0.0.0", port=8000):
        self.host = host
        self.port = port
        self.clients = set()
        self.logger = logging.getLogger(f"{__name__}")

    async def start(self):
        self.logger.info(f"WebSocket Server running on ws://{self.host}:{self.port}")
        async with websockets.serve(self._handler, self.host, self.port):
            await asyncio.Future()   # run forever

    async def _handler(self, websocket):
        # Client connect
        self.clients.add(websocket)
        self.logger.info("Client connected")
        await self.on_connect(websocket)

        try:
            async for message in websocket:
                self.logger.debug(f"Received from client: {message}")
                await self.on_message(websocket, message)

        except websockets.ConnectionClosed as e:
            self.logger.warning(f"Connection closed: {e}")
        
        except Exception as e:
            self.logger.error(f"WebSocket handler error: {e}")

        finally:
            # Client disconnect
            if websocket in self.clients:
                self.clients.remove(websocket)

            self.logger.info("Client disconnected")
            await self.on_disconnect(websocket)

    # ============== PUBLIC METHODS ==============
    async def send(self, websocket, data):
        """Send to specific client."""
        try:
            msg = json.dumps(data) if isinstance(data, dict) else str(data)
            await websocket.send(msg)
            self.logger.debug(f"Sent to client: {msg}")
        except Exception as e:
            self.logger.error(f"Error sending message: {e}")

    async def broadcast(self, data):
        """Send to all connected clients."""
        msg = json.dumps(data) if isinstance(data, dict) else str(data)
        self.logger.debug(f"Broadcasting: {msg}")

        if self.clients:
            try:
                await asyncio.gather(*(c.send(msg) for c in self.clients))
            except Exception as e:
                self.logger.error(f"Broadcast error: {e}")

    # ============== EVENT HOOKS ==============
    async def on_connect(self, ws):
        self.logger.info("on_connect: Client joined")
    
    async def on_message(self, ws, message):
        self.logger.debug(f"on_message: {message}")
    
    async def on_disconnect(self, ws):
        self.logger.info("on_disconnect: Client left")

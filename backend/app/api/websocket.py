"""
WebSocket endpoint for real-time updates.
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import asyncio
import json
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.active_connections: list[WebSocket] = []
        self._initialized = True

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients."""
        if not self.active_connections:
            return

        dead_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error sending message: {e}")
                dead_connections.append(connection)

        # Remove dead connections
        for connection in dead_connections:
            self.disconnect(connection)

    async def send_funding_rate_update(self, strategy_id: str, data: dict):
        """Send funding rate update."""
        await self.broadcast({
            "type": "funding_rate_update",
            "strategy_id": strategy_id,
            "data": data
        })

    async def send_position_update(self, strategy_id: str, data: dict):
        """Send position update."""
        await self.broadcast({
            "type": "position_update",
            "strategy_id": strategy_id,
            "data": data
        })

    async def send_strategy_status(self, strategy_id: str, status: str):
        """Send strategy status change."""
        await self.broadcast({
            "type": "strategy_status",
            "strategy_id": strategy_id,
            "status": status
        })


# Singleton instance
manager = ConnectionManager()


@router.websocket("/updates")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await manager.connect(websocket)

    try:
        # Send initial connection message
        await websocket.send_json({
            "type": "connected",
            "message": "Connected to funding rate dashboard",
            "timestamp": str(asyncio.get_event_loop().time())
        })

        # Keep connection alive
        while True:
            try:
                # Receive ping/pong or subscription messages
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)

                # Handle client messages (subscriptions, etc.)
                try:
                    msg = json.loads(data)
                    if msg.get("type") == "ping":
                        await websocket.send_json({"type": "pong"})
                except json.JSONDecodeError:
                    pass

            except asyncio.TimeoutError:
                # Send keepalive ping
                try:
                    await websocket.send_json({"type": "ping"})
                except:
                    break

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)

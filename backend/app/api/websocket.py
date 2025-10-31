"""
WebSocket endpoint for real-time updates.
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import asyncio
import json

router = APIRouter()


class ConnectionManager:
    """Manages WebSocket connections."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients."""
        dead_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                dead_connections.append(connection)

        # Remove dead connections
        for connection in dead_connections:
            self.active_connections.remove(connection)


manager = ConnectionManager()


@router.websocket("/updates")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await manager.connect(websocket)

    try:
        # Send initial connection message
        await websocket.send_json({
            "type": "connected",
            "message": "Connected to funding rate dashboard"
        })

        # Keep connection alive and listen for client messages
        while True:
            # Wait for messages from client (e.g., subscription requests)
            data = await websocket.receive_text()

            # Echo back for now (implement proper handling later)
            await websocket.send_json({
                "type": "echo",
                "data": data
            })

    except WebSocketDisconnect:
        manager.disconnect(websocket)

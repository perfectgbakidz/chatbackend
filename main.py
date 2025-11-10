from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from . import models
from .database import engine
from .auth import router as auth_router
from sqlalchemy.orm import Session
import json

# Create database tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="React Chat App Backend",
    description="Backend API for a real-time chat application using FastAPI and SQLite.",
    version="1.0.0"
)

# Allow CORS for React frontend
origins = [
    "http://localhost:5173",  # Vite React frontend
    "http://127.0.0.1:5173"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register authentication routes
app.include_router(auth_router)

# Optional: Define placeholder routes for chat and message endpoints
@app.get("/")
def home():
    return {"message": "Welcome to the React Chat App Backend API 🚀"}

# Example WebSocket manager for real-time events
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, user_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[user_id] = websocket

    def disconnect(self, user_id: str):
        if user_id in self.active_connections:
            del self.active_connections[user_id]

    async def send_personal_message(self, user_id: str, message: dict):
        websocket = self.active_connections.get(user_id)
        if websocket:
            await websocket.send_json(message)

    async def broadcast(self, message: dict):
        for connection in self.active_connections.values():
            await connection.send_json(message)

manager = ConnectionManager()

@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    """
    WebSocket connection for real-time messages.
    - user_id: authenticated user ID (client must pass it when connecting)
    """
    await manager.connect(user_id, websocket)
    await manager.broadcast({"event": "user_online", "user_id": user_id})

    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            await manager.broadcast(payload)
    except WebSocketDisconnect:
        manager.disconnect(user_id)
        await manager.broadcast({"event": "user_offline", "user_id": user_id})

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, status, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy import create_engine, Column, String, Text, DateTime, ForeignKey, Table
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Session
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta
from typing import List, Optional
import uuid, json

# ----------------------------------------------------------------------
# DATABASE CONFIGURATION (SQLite)
# ----------------------------------------------------------------------
DATABASE_URL = "sqlite:///./chat_app.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()

# ----------------------------------------------------------------------
# SECURITY CONFIGURATION (JWT ONLY — No password encryption)
# ----------------------------------------------------------------------
SECRET_KEY = "supersecretkey"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_access_token(token: str):
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None

# ----------------------------------------------------------------------
# DATABASE MODELS
# ----------------------------------------------------------------------
def gen_uuid():
    return str(uuid.uuid4())

chat_members = Table(
    "chat_members", Base.metadata,
    Column("chat_id", String, ForeignKey("chats.id")),
    Column("user_id", String, ForeignKey("users.id")),
)

class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=gen_uuid)
    email = Column(String, unique=True, index=True)
    username = Column(String, unique=True, index=True)
    displayName = Column(String)
    passwordHash = Column(String)  # Plain text password (no encryption)
    avatarUrl = Column(String, nullable=True)
    status = Column(String, nullable=True)
    lastSeen = Column(String, default="offline")
    createdAt = Column(DateTime, default=datetime.utcnow)
    chats = relationship("Chat", secondary=chat_members, back_populates="members")

class Chat(Base):
    __tablename__ = "chats"
    id = Column(String, primary_key=True, default=gen_uuid)
    type = Column(String)  # "individual" or "group"
    name = Column(String, nullable=True)
    avatarUrl = Column(String, nullable=True)
    createdAt = Column(DateTime, default=datetime.utcnow)
    members = relationship("User", secondary=chat_members, back_populates="chats")
    messages = relationship("Message", back_populates="chat", cascade="all, delete")

class Message(Base):
    __tablename__ = "messages"
    id = Column(String, primary_key=True, default=gen_uuid)
    chatId = Column(String, ForeignKey("chats.id"))
    senderId = Column(String, ForeignKey("users.id"))
    type = Column(String)  # "text" or "image"
    content = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)
    chat = relationship("Chat", back_populates="messages")

Base.metadata.create_all(bind=engine)

# ----------------------------------------------------------------------
# PYDANTIC SCHEMAS
# ----------------------------------------------------------------------
class UserCreate(BaseModel):
    email: EmailStr
    password: str
    username: str
    displayName: str

class UserOut(BaseModel):
    id: str
    email: EmailStr
    username: str
    displayName: str
    avatarUrl: Optional[str]
    status: Optional[str]
    class Config:
        orm_mode = True

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class MessageCreate(BaseModel):
    type: str
    content: str

class MessageOut(BaseModel):
    id: str
    chatId: str
    senderId: str
    type: str
    content: str
    timestamp: datetime
    class Config:
        orm_mode = True

class ChatOut(BaseModel):
    id: str
    type: str
    name: Optional[str]
    avatarUrl: Optional[str]
    createdAt: datetime
    members: List[UserOut]
    class Config:
        orm_mode = True

# ----------------------------------------------------------------------
# AUTHENTICATION ROUTES
# ----------------------------------------------------------------------
router = APIRouter(prefix="/auth", tags=["Auth"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = db.query(User).filter(User.id == payload.get("sub")).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.post("/signup", response_model=Token, status_code=201)
def signup(user: UserCreate, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == user.email).first():
        raise HTTPException(400, "Email already registered")
    new_user = User(
        email=user.email,
        username=user.username,
        displayName=user.displayName,
        passwordHash=user.password  # Store password directly
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    token = create_access_token({"sub": new_user.id})
    return {"access_token": token, "token_type": "bearer"}

@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or user.passwordHash != form_data.password:
        raise HTTPException(401, "Invalid credentials")
    token = create_access_token({"sub": user.id})
    return {"access_token": token, "token_type": "bearer"}

# ----------------------------------------------------------------------
# MAIN APP INITIALIZATION
# ----------------------------------------------------------------------
app = FastAPI(title="React Chat App Backend (SQLite - No Password Encryption)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

@app.get("/")
def home():
    return {"message": "Welcome to the React Chat App Backend API (Plain Password Version) 🚀"}

# ----------------------------------------------------------------------
# SIMPLE WEBSOCKET MANAGER (Real-time Messaging)
# ----------------------------------------------------------------------
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

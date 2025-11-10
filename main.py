from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Table
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base
import uuid

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
    passwordHash = Column(String)
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

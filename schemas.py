from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import List, Optional

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

from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional
from datetime import datetime
from decimal import Decimal


# Token相关
class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LoginResponse(Token):
    """登录/注册响应：在 Token 基础上附带用户信息，前端 setAuth 需要 user。"""
    user: "UserResponse"


class TokenPayload(BaseModel):
    sub: int
    type: str
    exp: datetime


class RefreshTokenRequest(BaseModel):
    refresh_token: str


# 用户认证相关
class UserRegister(BaseModel):
    email: EmailStr
    nickname: str = Field(..., min_length=2, max_length=50)
    password: str = Field(..., min_length=6, max_length=50)
    school_id: int


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
    nickname: str
    avatar_url: Optional[str] = None
    school_id: int
    role: str
    bio: Optional[str] = None
    is_active: bool
    created_at: datetime
    reputation_score: Optional[Decimal] = None

    class Config:
        from_attributes = True


class LoginResponse(Token):
    """登录/注册响应：在 Token 基础上附带用户信息，前端 setAuth 需要 user。"""
    user: UserResponse


class UserUpdate(BaseModel):
    nickname: Optional[str] = Field(None, min_length=2, max_length=50)
    bio: Optional[str] = Field(None, max_length=200)
    avatar_url: Optional[str] = None

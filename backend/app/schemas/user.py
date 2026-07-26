from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional
from datetime import datetime


# Token相关
class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


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
    # ACC-01.2: school_id 改为可选，优先从 X-School-Code 头解析（TEN-02 写请求忽略 body）
    # 未提供 X-School-Code 且 school_id 为 None 时，register 端点返回 400
    school_id: Optional[int] = None
    # ACC-01.2: 邀请码可选字段；前端通过 URL ?invite=xxx 写入短期上下文后回传
    # 提供时将校验有效性（存在/未过期/未使用/邮箱匹配/学校匹配）并消费，
    # 同时为注册用户在该学校创建 active membership
    invite_code: Optional[str] = Field(
        None,
        max_length=64,
        description="邀请码（可选）；提供时将校验并消费，同时创建 membership",
    )


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

    model_config = ConfigDict(from_attributes=True)


class LoginResponse(Token):
    """登录/注册响应：在 Token 基础上附带用户信息，前端 setAuth 需要 user。"""
    user: UserResponse


class UserUpdate(BaseModel):
    nickname: Optional[str] = Field(None, min_length=2, max_length=50)
    bio: Optional[str] = Field(None, max_length=200)
    avatar_url: Optional[str] = None


# ACC-01.3: 找回密码
class ForgotPasswordRequest(BaseModel):
    """发起找回密码：提交邮箱。

    后端无论邮箱是否存在都返回相同消息，避免泄露账号存在性。
    本地开发环境会在响应中返回 token（无邮件服务）。
    """
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """重置密码：提交 token + 新密码。"""
    token: str = Field(..., min_length=10, description="找回密码 Token")
    new_password: str = Field(..., min_length=6, max_length=50, description="新密码（至少 6 位）")


class ForgotPasswordResponse(BaseModel):
    """找回密码响应。

    production：固定返回 message，不泄露账号是否存在；
    本地开发（DEBUG=true 或 APP_ENV=opengauss/demo）：附加 reset_token 便于测试。
    """
    message: str
    reset_token: Optional[str] = Field(
        None, description="仅本地开发环境返回；production 不返回"
    )


class ResetPasswordResponse(BaseModel):
    """重置密码响应。"""
    message: str

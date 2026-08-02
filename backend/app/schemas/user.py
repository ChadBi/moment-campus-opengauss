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
    # 2026-08-01 起：注册时用户自由选择初始加入的学校，通过 school_id 显式指定；
    # 未提供时回退到 X-School-Code 头解析（兼容既有调用方），两者皆无则 400。
    # 注册成功后为该用户创建所选学校的 active membership（is_default=True）。
    school_id: Optional[int] = None


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
    # ACC-01.4: 首次使用引导标记（前端 FirstUseGuide 据此决定是否弹出教程）
    onboarding_completed: bool = False

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

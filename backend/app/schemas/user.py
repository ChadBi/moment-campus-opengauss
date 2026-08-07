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
    # B-01: 校园身份认证状态（前端据此展示认证徽标/入口）
    campus_verified: bool = False

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


# B-01: 校园身份认证（统一教育邮箱：认证用登录邮箱发码，无需单独邮箱/学号）
class CampusVerifySendRequest(BaseModel):
    """发起校园身份认证：使用当前登录邮箱（须命中该校允许域名）。"""
    pass


class CampusVerifySendResponse(BaseModel):
    """校园身份认证 send 响应。

    production（SMTP 已配置）：仅 message，验证邮件已发送。
    本地开发（APP_ENV in opengauss/demo/test 或 DEBUG=true 或 SMTP 未配置）：
    附加 6 位 code 便于测试链路打通（无邮件服务）。
    """
    message: str
    code: Optional[str] = Field(None, description="6 位验证码；仅本地开发环境返回")


class CampusVerifyConfirmRequest(BaseModel):
    """确认校园身份认证：提交 6 位数字验证码。"""
    code: Optional[str] = Field(
        None,
        min_length=6,
        max_length=6,
        pattern=r"^\d{6}$",
        description="6 位数字验证码",
    )


class CampusVerifyConfirmResponse(BaseModel):
    """校园身份认证 confirm 响应。"""
    message: str
    campus_verified: bool = True

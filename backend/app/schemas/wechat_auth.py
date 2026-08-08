from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Literal, Optional
from datetime import datetime


class WechatExchangeRequest(BaseModel):
    """微信 code2Session 请求：小程序端通过 wx.login() 获取 code 后发送到后端。"""
    code: str = Field(..., min_length=6, max_length=128, description="wx.login() 获取的临时 code")


class WechatPhoneLoginRequest(BaseModel):
    """微信登录并授权手机号。"""
    code: str = Field(..., min_length=1, max_length=128, description="wx.login() 获取的 code")
    phone_code: str = Field(..., min_length=1, max_length=256, description="getPhoneNumber 返回的 code")
    school_code: Optional[str] = Field(None, max_length=50)


class WechatSmsLoginRequest(BaseModel):
    """微信会话 + 手机号短信验证码绑定登录。"""

    code: str = Field(..., min_length=1, max_length=128, description="wx.login() 获取的 code")
    phone: str = Field(..., min_length=11, max_length=11, pattern=r"^1\d{10}$")
    sms_code: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")
    school_code: Optional[str] = Field(None, max_length=50)


class WechatPhoneLoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict


class WechatQuickLoginResponse(BaseModel):
    """微信 OpenID 快速登录结果；未绑定时引导手机号绑定。"""

    status: Literal["authenticated", "binding_required"]
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    user: Optional[dict] = None
    message: Optional[str] = None


class WechatExchangeBoundResponse(BaseModel):
    """已绑定用户直接登录成功响应。"""
    status: str = "authenticated"
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: int
    user: dict


class WechatExchangeUnboundResponse(BaseModel):
    """未绑定用户返回 binding_ticket，引导绑定流程。"""
    status: str = "binding_required"
    binding_ticket: str
    expires_in: int = 300


class WechatBindExistingRequest(BaseModel):
    """绑定已有 Web 账号请求。"""
    binding_ticket: str = Field(..., min_length=32, description="微信返回的 binding_ticket")
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=50)


class WechatBindExistingResponse(BaseModel):
    """绑定成功响应（直接签发 JWT）。"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: int
    user: dict
    message: str = "绑定成功"


class WechatRegisterRequest(BaseModel):
    """微信新用户注册请求。"""
    binding_ticket: str = Field(..., min_length=32, description="微信返回的 binding_ticket")
    nickname: str = Field(..., min_length=2, max_length=50)
    school_id: int
    password: str = Field(..., min_length=6, max_length=50, description="设置 Web 端登录密码")
    email: Optional[EmailStr] = Field(None, description="可选邮箱（不填自动生成）")


class WechatRegisterResponse(BaseModel):
    """微信注册成功响应。"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: int
    user: dict
    message: str = "注册成功"


class IdentityResponse(BaseModel):
    """身份信息响应。"""
    id: int
    identity_type: str
    identity_key: str
    openid: Optional[str] = None
    unionid: Optional[str] = None
    created_at: datetime
    last_used_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class IdentityListResponse(BaseModel):
    """身份列表响应。"""
    identities: list[IdentityResponse]


class AddEmailIdentityRequest(BaseModel):
    """添加邮箱登录方式。"""
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=50)


class AddEmailIdentityResponse(BaseModel):
    """添加成功响应。"""
    message: str
    identity_id: int


class SessionResponse(BaseModel):
    """会话信息响应。"""
    id: int
    session_type: str
    client_ip: Optional[str] = None
    user_agent: Optional[str] = None
    device_id: Optional[str] = None
    device_info: Optional[str] = None
    expires_at: datetime
    last_active_at: Optional[datetime] = None
    created_at: datetime
    is_current: bool = False

    model_config = ConfigDict(from_attributes=True)


class SessionListResponse(BaseModel):
    """会话列表响应。"""
    sessions: list[SessionResponse]


class LogoutAllResponse(BaseModel):
    """退出全部设备响应。"""
    message: str
    revoked_count: int

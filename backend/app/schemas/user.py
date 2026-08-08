from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator, model_validator
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
    phone: str
    sms_code: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")
    password: str = Field(..., min_length=6, max_length=50)
    password_confirm: str = Field(..., min_length=6, max_length=50)
    # 2026-08-01 起：注册时用户自由选择初始加入的学校，通过 school_id 显式指定；
    # 未提供时回退到 X-School-Code 头解析（兼容既有调用方），两者皆无则 400。
    # 注册成功后为该用户创建所选学校的 active membership（is_default=True）。
    school_id: Optional[int] = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        value = value.strip()
        if not value.isdigit() or len(value) != 11 or not value.startswith("1"):
            raise ValueError("请输入有效的国内 11 位手机号")
        return value

    @model_validator(mode="after")
    def validate_password_confirmation(self):
        if self.password != self.password_confirm:
            raise ValueError("两次输入的密码不一致")
        return self


class UserLogin(BaseModel):
    phone: str
    password: Optional[str] = Field(None, min_length=6, max_length=50)
    sms_code: Optional[str] = Field(None, min_length=6, max_length=6, pattern=r"^\d{6}$")

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        value = value.strip()
        if not value.isdigit() or len(value) != 11 or not value.startswith("1"):
            raise ValueError("请输入有效的国内 11 位手机号")
        return value

    @model_validator(mode="after")
    def require_one_login_method(self):
        if bool(self.password) == bool(self.sms_code):
            raise ValueError("请选择密码登录或短信验证码登录")
        return self


class SmsSendRequest(BaseModel):
    phone: str
    purpose: str = Field(..., pattern=r"^(register|login|set_password|education_unbind)$")

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        value = value.strip()
        if not value.isdigit() or len(value) != 11 or not value.startswith("1"):
            raise ValueError("请输入有效的国内 11 位手机号")
        return value


class SmsSendResponse(BaseModel):
    message: str
    out_id: Optional[str] = None
    code: Optional[str] = Field(None, description="仅 Mock/本地开发返回，生产环境不返回")


class PasswordSetRequest(BaseModel):
    password: str = Field(..., min_length=6, max_length=50)
    password_confirm: str = Field(..., min_length=6, max_length=50)
    sms_code: Optional[str] = Field(None, min_length=6, max_length=6, pattern=r"^\d{6}$")

    @model_validator(mode="after")
    def validate_password_confirmation(self):
        if self.password != self.password_confirm:
            raise ValueError("两次输入的密码不一致")
        return self


class UserResponse(BaseModel):
    id: int
    phone: Optional[str] = None
    education_email: Optional[str] = None
    has_password: bool = False
    nickname: str
    avatar_url: Optional[str] = None
    school_id: int
    registration_school_id: Optional[int] = None
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
    phone: str


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


# B-01: 校园身份认证（教育邮箱只用于认证，不作为登录凭证）
class CampusVerifySendRequest(BaseModel):
    """发起校园身份认证：提交当前学校允许的教育邮箱。"""
    education_email: EmailStr


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


class EducationEmailUnbindSendRequest(BaseModel):
    """解除教育邮箱绑定前的手机号短信确认。"""
    pass


class EducationEmailUnbindRequest(BaseModel):
    sms_code: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")

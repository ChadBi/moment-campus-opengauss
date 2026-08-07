"""B-01: SMTP 邮件发送服务（校园身份认证验证邮件）

配置（仅存 .env.opengauss，不进文档/Git）：
    SMTP_HOST / SMTP_PORT / SMTP_USER / SMTP_PASS（QQ 邮箱授权码）/ SMTP_FROM

未配置 SMTP_HOST 时视为"无邮件能力"：send_verification_email 返回 False，
由调用方（verify-campus/send）回退为 dev 直接返回验证码（演示闭环）。
"""
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

from app.config import settings


def smtp_configured() -> bool:
    """SMTP 是否已配置（host/user/pass 齐全）"""
    return bool(settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASS)


def build_verification_email(
    to_email: str,
    school_name: str,
    code: str,
) -> MIMEMultipart:
    """构造校园身份认证验证邮件（HTML）。"""
    msg = MIMEMultipart("alternative")
    from_addr = settings.SMTP_FROM or settings.SMTP_USER
    msg["From"] = formataddr(("此刻校园", from_addr))
    msg["To"] = to_email
    msg["Subject"] = f"【此刻校园】{school_name} 校园身份认证"

    html = f"""<div style="font-family:'PingFang SC','Microsoft YaHei',sans-serif;max-width:600px;margin:0 auto;padding:24px;border:1px solid #e5e7eb;border-radius:12px;">
  <h2 style="color:#1B4332;margin:0 0 16px;">此刻校园 · 校园身份认证</h2>
  <p style="color:#374151;line-height:1.7;">你好：</p>
  <p style="color:#374151;line-height:1.7;">
    你正在为 <b>{school_name}</b> 的账号完成校园身份认证。
    请在此刻校园个人中心输入下面的 6 位验证码完成认证（10 分钟内有效）：
  </p>
  <p style="text-align:center;margin:24px 0;font-size:32px;font-weight:700;letter-spacing:8px;color:#1B4332;">
    {code}
  </p>
  <p style="color:#6b7280;font-size:13px;line-height:1.7;">
    如果不是本人操作，请忽略此邮件。验证码使用一次后立即失效。
  </p>
  <p style="color:#9ca3af;font-size:12px;margin-top:24px;">
    此邮件由系统自动发送，请勿回复。若非本人操作，请忽略本邮件。
  </p>
</div>"""
    msg.attach(MIMEText(html, "html", "utf-8"))
    return msg


def send_verification_email(
    to_email: str,
    school_name: str,
    code: str,
) -> bool:
    """发送只包含 6 位验证码的验证邮件；未配置 SMTP 时返回 False。

    使用 smtplib.SMTP_SSL（QQ 邮箱 smtp.qq.com:465）。超时 15s。
    """
    if not smtp_configured():
        return False

    msg = build_verification_email(to_email, school_name, code)
    from_addr = settings.SMTP_FROM or settings.SMTP_USER

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(
            settings.SMTP_HOST, settings.SMTP_PORT, timeout=15, context=context
        ) as server:
            server.login(settings.SMTP_USER, settings.SMTP_PASS)
            server.sendmail(from_addr, [to_email], msg.as_string())
        return True
    except Exception:
        # 邮件发送失败不阻塞认证主流程：调用方回退 dev 展示验证码
        return False

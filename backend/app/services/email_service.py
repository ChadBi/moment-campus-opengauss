"""B-01: SMTP 邮件发送服务（校园身份认证验证邮件）

配置（仅存 .env.opengauss，不进文档/Git）：
    SMTP_HOST / SMTP_PORT / SMTP_USER / SMTP_PASS（QQ 邮箱授权码）/ SMTP_FROM / APP_BASE_URL

未配置 SMTP_HOST 时视为"无邮件能力"：send_verification_email 返回 False，
由调用方（verify-campus/send）回退为 dev 直接返回验证链接/验证码（演示闭环）。
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
    verify_link: str,
    school_name: str,
    code: str | None = None,
) -> MIMEMultipart:
    """构造校园身份认证验证邮件（HTML）。"""
    msg = MIMEMultipart("alternative")
    from_addr = settings.SMTP_FROM or settings.SMTP_USER
    msg["From"] = formataddr(("此刻校园", from_addr))
    msg["To"] = to_email
    msg["Subject"] = f"【此刻校园】{school_name} 校园身份认证"

    code_block = ""
    if code:
        code_block = (
            f'<p style="margin:8px 0;">或使用验证码：<b style="font-size:20px;'
            f'letter-spacing:2px;">{code}</b>（10 分钟内有效）</p>'
        )

    html = f"""<div style="font-family:'PingFang SC','Microsoft YaHei',sans-serif;max-width:600px;margin:0 auto;padding:24px;border:1px solid #e5e7eb;border-radius:12px;">
  <h2 style="color:#1B4332;margin:0 0 16px;">此刻校园 · 校园身份认证</h2>
  <p style="color:#374151;line-height:1.7;">你好：</p>
  <p style="color:#374151;line-height:1.7;">
    你正在为 <b>{school_name}</b> 的账号完成校园身份认证。
    请点击下方按钮完成验证（链接 10 分钟内有效）：
  </p>
  <p style="text-align:center;margin:24px 0;">
    <a href="{verify_link}" style="display:inline-block;background:#1B4332;color:#ffffff;padding:12px 32px;border-radius:8px;text-decoration:none;font-size:15px;">
      完成校园身份认证
    </a>
  </p>
  {code_block}
  <p style="color:#6b7280;font-size:13px;line-height:1.7;">
    如果按钮无法点击，请复制以下链接到浏览器打开：<br/>
    <a href="{verify_link}" style="color:#1B4332;word-break:break-all;">{verify_link}</a>
  </p>
  <p style="color:#9ca3af;font-size:12px;margin-top:24px;">
    此邮件由系统自动发送，请勿回复。若非本人操作，请忽略本邮件。
  </p>
</div>"""
    msg.attach(MIMEText(html, "html", "utf-8"))
    return msg


def send_verification_email(
    to_email: str,
    verify_link: str,
    school_name: str,
    code: str | None = None,
) -> bool:
    """发送验证邮件；未配置 SMTP 时返回 False（调用方回退 dev 展示）。

    使用 smtplib.SMTP_SSL（QQ 邮箱 smtp.qq.com:465）。超时 15s。
    """
    if not smtp_configured():
        return False

    msg = build_verification_email(to_email, verify_link, school_name, code)
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
        # 邮件发送失败不阻塞认证主流程：调用方回退 dev 展示验证链接
        return False

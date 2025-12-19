import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr

from app.config import settings


def get_from_address() -> str:
    """Get formatted from address with display name."""
    email = settings.smtp_from_email or settings.smtp_user
    if settings.smtp_from_name:
        return formataddr((settings.smtp_from_name, email))
    return email


def send_otp_email(to_email: str, otp: str, full_name: str) -> bool:
    """Send OTP via email using Gmail SMTP."""
    if not settings.smtp_user or not settings.smtp_password:
        # Development mode: just print to console
        print(f"[DEV MODE] OTP for {to_email}: {otp}")
        return True

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Your Verification Code"
        msg["From"] = get_from_address()
        msg["To"] = to_email

        text = f"""
Hello {full_name},

Your verification code is: {otp}

This code will expire in {settings.otp_expire_minutes} minutes.

If you didn't request this code, please ignore this email.

Best regards,
Education App Team
"""

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        .container {{ font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; }}
        .otp-code {{ font-size: 32px; font-weight: bold; color: #2563eb; letter-spacing: 8px; text-align: center; padding: 20px; background: #f3f4f6; border-radius: 8px; margin: 20px 0; }}
        .footer {{ color: #6b7280; font-size: 12px; margin-top: 30px; }}
    </style>
</head>
<body>
    <div class="container">
        <h2>Hello {full_name},</h2>
        <p>Your verification code is:</p>
        <div class="otp-code">{otp}</div>
        <p>This code will expire in <strong>{settings.otp_expire_minutes} minutes</strong>.</p>
        <p>If you didn't request this code, please ignore this email.</p>
        <div class="footer">
            <p>Best regards,<br>Education App Team</p>
        </div>
    </div>
</body>
</html>
"""

        msg.attach(MIMEText(text, "plain"))
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(settings.smtp_user, to_email, msg.as_string())

        return True

    except Exception as e:
        print(f"Failed to send email: {e}")
        return False


def send_password_reset_email(to_email: str, otp: str, full_name: str) -> bool:
    """Send password reset OTP via email."""
    if not settings.smtp_user or not settings.smtp_password:
        # Development mode: just print to console
        print(f"[DEV MODE] Password Reset OTP for {to_email}: {otp}")
        return True

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Password Reset Code"
        msg["From"] = get_from_address()
        msg["To"] = to_email

        text = f"""
Hello {full_name},

You requested a password reset. Your verification code is: {otp}

This code will expire in {settings.otp_expire_minutes} minutes.

If you didn't request this, please ignore this email and your password will remain unchanged.

Best regards,
Education App Team
"""

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        .container {{ font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; }}
        .otp-code {{ font-size: 32px; font-weight: bold; color: #dc2626; letter-spacing: 8px; text-align: center; padding: 20px; background: #fef2f2; border-radius: 8px; margin: 20px 0; }}
        .footer {{ color: #6b7280; font-size: 12px; margin-top: 30px; }}
    </style>
</head>
<body>
    <div class="container">
        <h2>Hello {full_name},</h2>
        <p>You requested a password reset. Your verification code is:</p>
        <div class="otp-code">{otp}</div>
        <p>This code will expire in <strong>{settings.otp_expire_minutes} minutes</strong>.</p>
        <p>If you didn't request this, please ignore this email and your password will remain unchanged.</p>
        <div class="footer">
            <p>Best regards,<br>Education App Team</p>
        </div>
    </div>
</body>
</html>
"""

        msg.attach(MIMEText(text, "plain"))
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(settings.smtp_user, to_email, msg.as_string())

        return True

    except Exception as e:
        print(f"Failed to send email: {e}")
        return False

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

def send_pro_plan_upgrade_email(to_email: str, full_name: str) -> bool:
    """Send Pro plan upgrade notification email."""
    if not settings.smtp_user or not settings.smtp_password:
        # Development mode: just print to console
        print(f"[DEV MODE] Pro Plan Upgrade Email for {to_email}")
        return True

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "🎉 Welcome to Pro Plan - Free Upgrade!"
        msg["From"] = get_from_address()
        msg["To"] = to_email

        text = f"""
Hello {full_name},

Congratulations! 🎉

We're excited to inform you that your account has been upgraded to our Pro Plan - absolutely FREE!

With the Pro Plan, you now have access to:
✓ Unlimited test generation
✓ All premium question banks
✓ Advanced analytics and performance tracking
✓ Priority support
✓ And much more!

Start exploring your Pro features now and take your learning to the next level.

Best regards,
Education App Team
"""

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        .container {{ font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 8px; text-align: center; }}
        .badge {{ display: inline-block; background: #fbbf24; color: #78350f; padding: 8px 16px; border-radius: 20px; font-weight: bold; font-size: 14px; margin-top: 10px; }}
        .features {{ background: #f9fafb; padding: 20px; border-radius: 8px; margin: 20px 0; }}
        .feature-item {{ margin: 12px 0; padding-left: 30px; position: relative; }}
        .feature-item:before {{ content: "✓"; position: absolute; left: 0; color: #10b981; font-weight: bold; font-size: 20px; }}
        .footer {{ color: #6b7280; font-size: 12px; margin-top: 30px; text-align: center; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1 style="margin: 0;">🎉 Congratulations!</h1>
            <p style="margin: 10px 0;">You've been upgraded to</p>
            <div class="badge">PRO PLAN - FREE</div>
        </div>

        <h2 style="color: #1f2937; margin-top: 30px;">Hello {full_name},</h2>

        <p style="color: #4b5563; line-height: 1.6;">
            We're excited to inform you that your account has been upgraded to our <strong>Pro Plan</strong> - absolutely FREE!
        </p>

        <div class="features">
            <h3 style="margin-top: 0; color: #1f2937;">Your Pro Features:</h3>
            <div class="feature-item">Unlimited test generation</div>
            <div class="feature-item">All premium question banks</div>
            <div class="feature-item">Advanced analytics and performance tracking</div>
            <div class="feature-item">Priority support</div>
            <div class="feature-item">Exclusive learning resources</div>
        </div>

        <p style="color: #4b5563; line-height: 1.6;">
            Start exploring your Pro features now and take your learning to the next level!
        </p>

        <div class="footer">
            <p>Best regards,<br><strong>Education App Team</strong></p>
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
        print(f"Failed to send Pro plan email: {e}")
        return False

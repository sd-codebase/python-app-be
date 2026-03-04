import httpx

from app.config import settings


async def send_whatsapp_otp(phone_number: str, otp: str) -> bool:
    """
    Send OTP via WhatsApp Business API.

    In development mode, only logs to console.
    In production mode, sends actual WhatsApp message via Graph API.

    Args:
        phone_number: Full phone number with country code (e.g. "919876543210")
        otp: The OTP code to send

    Returns:
        True if successful, False otherwise
    """
    if settings.notification_mode == "development":
        print(f"\n{'='*50}")
        print(f"[WHATSAPP] Development mode - Message would be sent to: {phone_number}")
        print(f"[WHATSAPP] OTP: {otp}")
        print(f"{'='*50}\n")
        return True

    try:
        url = f"https://graph.facebook.com/v22.0/{settings.whatsapp_phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {settings.whatsapp_api_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": phone_number,
            "type": "template",
            "template": {
                "name": settings.whatsapp_template_name,
                "language": {"code": settings.whatsapp_template_language},
                "components": [
                    {
                        "type": "body",
                        "parameters": [
                            {"type": "text", "text": otp},
                            {"type": "text", "text": settings.whatsapp_app_name},
                            {"type": "text", "text": "10 Minutes"},
                            {"type": "text", "text": settings.whatsapp_contact_number},
                        ],
                    },
                    {
                        "type": "button",
                        "sub_type": "url",
                        "index": 0,
                        "parameters": [
                            {"type": "text", "text": otp}
                        ],
                    },
                ],
            },
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers, timeout=30)

        if response.status_code == 200:
            print(f"[WHATSAPP] OTP sent successfully to {phone_number}")
            return True
        else:
            print(f"[WHATSAPP] Failed to send OTP to {phone_number}: {response.status_code} {response.text}")
            return False

    except Exception as e:
        print(f"[WHATSAPP] Failed to send OTP to {phone_number}: {str(e)}")
        return False

"""Simple email service for sending welcome emails via Resend."""

import resend
from airweave.core.config import settings
from airweave.core.logging import logger


async def send_welcome_email(to_email: str, user_name: str) -> None:
    """Send a welcome email to a new user.
    
    Only works when RESEND_API_KEY is configured (production only).
    """
    if not settings.RESEND_API_KEY:
        logger.debug("RESEND_API_KEY not configured - skipping welcome email")
        return
    
    try:
        resend.api_key = settings.RESEND_API_KEY
        
        resend.Emails.send({
            "from": settings.RESEND_FROM_EMAIL,
            "to": [to_email],
            "subject": "Welcome to Airweave! 🎉",
            "html": f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                <h1 style="color: #2563eb;">Welcome to Airweave, {user_name}! 🎉</h1>
                <p>Thank you for joining Airweave! We're excited to help you make any app searchable for your agent.</p>
                <p>Ready to get started? <a href="{settings.app_url}/onboarding" style="background: #2563eb; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Get Started</a></p>
                <p>Best regards,<br>The Airweave Team</p>
            </div>
            """
        })
        
        logger.info(f"Welcome email sent to {to_email}")
    except Exception as e:
        logger.warning(f"Failed to send welcome email to {to_email}: {e}")

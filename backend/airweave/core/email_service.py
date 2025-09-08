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
            "subject": "Welcome to Airweave",
            "html": f"""
<div style="font-family: Arial, sans-serif; font-size: 10pt;">
    <p style="margin: 0 0 15px 0;">
        Hey,
    </p>
    
    <p style="margin: 0 0 15px 0;">
        Thanks for signing up, this is Lennert (co-founder at Airweave).
    </p>

    <p style="margin: 0 0 15px 0;">
        Here's some useful stuff to get you started:
    </p>
    
    <p style="margin: 0 0 8px 0;">
        • Our docs: <a href="https://docs.airweave.ai/welcome" style="color: #0000EE; text-decoration: underline;">https://docs.airweave.ai/welcome</a>
    </p>
    <p style="margin: 0 0 8px 0;">
        • Our repo: <a href="https://github.com/airweave-ai/airweave" style="color: #0000EE; text-decoration: underline;">https://github.com/airweave-ai/airweave</a>
    </p>
    <p style="margin: 0 0 15px 0;">
        • Our discord: <a href="https://discord.com/invite/6wDWUhhuu2" style="color: #0000EE; text-decoration: underline;">https://discord.com/invite/6wDWUhhuu2</a>
    </p>

    <p style="margin: 15px 0;">
        Let me know if you need anything or have any questions.
    </p>
    
    <p style="margin: 15px 0 0 0;">
        Btw, if you want to see Airweave in action or just chat about what you're building, feel free to book some time with me here: <a href="https://cal.com/lennert-airweave/airweave-demo" style="color: #0000EE; text-decoration: underline;">https://cal.com/lennert-airweave/airweave-demo</a>
    </p>
    
    <p style="margin: 15px 0 0 0;">
        Lennert<br>
    </p>
</div>
            """
        })
        
        logger.info(f"Welcome email sent to {to_email}")
    except Exception as e:
        logger.warning(f"Failed to send welcome email to {to_email}: {e}")

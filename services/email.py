"""Optional email notifications via Resend."""

import logging
import os

import requests

logger = logging.getLogger(__name__)

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", "Arcane Forge <notifications@arcaneforge.app>")


def send_campaign_complete_email(to_email: str, job_id: str, campaign_url: str) -> bool:
    if not RESEND_API_KEY or not to_email:
        return False
    try:
        resp = requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
            json={
                "from": FROM_EMAIL,
                "to": [to_email],
                "subject": "Your Arcane Forge campaign is ready",
                "html": (
                    f"<p>Your campaign (job {job_id[:8]}...) has finished generating.</p>"
                    f'<p><a href="{campaign_url}">View your campaign</a></p>'
                ),
            },
            timeout=15,
        )
        resp.raise_for_status()
        return True
    except Exception as exc:
        logger.warning("Failed to send email: %s", exc)
        return False

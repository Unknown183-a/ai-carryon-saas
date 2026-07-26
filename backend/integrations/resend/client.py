"""
Resend transactional email client — same pattern as
`integrations/elevenlabs/client.py` and the other integrations: one
function, raw args in, no SDK, httpx directly against Resend's REST API
(https://resend.com/docs/api-reference/emails/send-email).

Env vars required: RESEND_API_KEY, ALERT_EMAIL_FROM
ALERT_EMAIL_TO is read by the caller (alert_agent.py), not here — this
module only knows how to send one email to one address; who the alert
actually goes to is a policy decision, not a transport one.

Chosen in Phase 10's scoping conversation over Gmail SMTP / SendGrid —
modern API, no SMTP session management, generous free tier for what
should be low-volume alert traffic (this is not a marketing-email
sender).
"""

from __future__ import annotations

import os

import httpx

RESEND_SEND_URL = "https://api.resend.com/emails"


def send_alert_email(to: str, subject: str, html_body: str, timeout: float = 15.0) -> dict:
    """Sends one email. Raises on any transport/HTTP error — same
    "one attempt, raise on failure" convention as
    `elevenlabs/client.py`'s `generate_speech`. alert_agent.py is the
    caller, and it already has its own retry-then-escalate policy (the
    whole reason Phase 10 exists) — this function doesn't need a second,
    competing retry loop of its own.
    """
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        raise RuntimeError("RESEND_API_KEY is not set. Add it to .env to enable alert emails.")

    from_address = os.environ.get("ALERT_EMAIL_FROM")
    if not from_address:
        raise RuntimeError("ALERT_EMAIL_FROM is not set. Add it to .env to enable alert emails.")

    response = httpx.post(
        RESEND_SEND_URL,
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "from": from_address,
            "to": [to],
            "subject": subject,
            "html": html_body,
        },
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()

import resend

from app.config import settings


def send_email(to: str, subject: str, html_body: str) -> dict:
    """Send a transactional email via Resend and return the API response."""
    resend.api_key = settings.resend_api_key

    params: resend.Emails.SendParams = {
        "from": "OpenLaw <noreply@openlaw.ai>",
        "to": [to],
        "subject": subject,
        "html": html_body,
    }

    response = resend.Emails.send(params)
    return response

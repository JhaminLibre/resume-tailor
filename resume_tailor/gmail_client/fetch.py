import base64
from resume_tailor.gmail_client.auth import get_gmail_service, require_gmail_credentials


def fetch_linkedin_alerts(max_results: int = 10) -> list[dict]:
    """Fetch LinkedIn job-alert emails from Gmail.

    Args:
        max_results: Maximum number of emails to fetch

    Returns:
        List of email dicts with keys: id, from, subject, received_at, body_html
    """
    require_gmail_credentials()
    service = get_gmail_service()

    query = 'from:jobalerts-noreply@linkedin.com (-subject:"your job alert") newer_than:2d'

    results = service.users().messages().list(userId="me", q=query, maxResults=max_results).execute()

    messages = results.get("messages", [])
    emails = []

    for msg in messages:
        msg_id = msg["id"]
        full_msg = service.users().messages().get(userId="me", id=msg_id, format="full").execute()

        headers = full_msg["payload"]["headers"]
        header_dict = {h["name"]: h["value"] for h in headers}

        body_html = ""
        if "parts" in full_msg["payload"]:
            for part in full_msg["payload"]["parts"]:
                if part["mimeType"] == "text/html":
                    data = part["body"].get("data", "")
                    if data:
                        body_html = base64.urlsafe_b64decode(data).decode("utf-8")
                    break
        else:
            data = full_msg["payload"]["body"].get("data", "")
            if data:
                body_html = base64.urlsafe_b64decode(data).decode("utf-8")

        email = {
            "id": msg_id,
            "from": header_dict.get("From", ""),
            "subject": header_dict.get("Subject", ""),
            "received_at": header_dict.get("Date", ""),
            "body_html": body_html,
        }
        emails.append(email)

    return emails

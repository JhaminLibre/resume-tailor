import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from resume_tailor.config import GMAIL_CREDENTIALS_PATH, GMAIL_TOKEN_PATH

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def get_gmail_service():
    """Get an authenticated Gmail API service.

    On first run, opens a browser for OAuth consent and caches the token.
    On subsequent runs, auto-refreshes the cached token.

    Returns:
        Authorized Gmail service object
    """
    creds = None

    if GMAIL_TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(GMAIL_TOKEN_PATH, SCOPES)

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    elif not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(
            GMAIL_CREDENTIALS_PATH,
            SCOPES,
            redirect_uri="http://localhost:8080/",
        )
        auth_url, _ = flow.authorization_url(prompt='consent')
        print("\n🔐 Google OAuth Authorization Required")
        print("=" * 60)
        print("1. Copy this URL and paste it into your browser:")
        print(f"\n{auth_url}\n")
        print("2. Log in and approve access")
        print("3. Copy the authorization code from the URL (after 'code=')")
        print("4. Paste it here:")
        print("=" * 60)
        code = input("Authorization code: ").strip()
        creds = flow.fetch_token(code=code)

    if creds:
        creds.to_json(GMAIL_TOKEN_PATH)

    from googleapiclient.discovery import build

    return build("gmail", "v1", credentials=creds)


def require_gmail_credentials():
    """Check that Gmail credentials file exists; raise error if not."""
    if not GMAIL_CREDENTIALS_PATH.exists():
        raise FileNotFoundError(
            f"Gmail credentials not found: {GMAIL_CREDENTIALS_PATH}\n\n"
            "To set up Gmail access:\n"
            "1. Go to console.cloud.google.com\n"
            "2. Create a new project\n"
            "3. Enable the Gmail API\n"
            "4. Create an OAuth 2.0 Desktop app credential\n"
            "5. Download the JSON and save to: " + str(GMAIL_CREDENTIALS_PATH)
        )

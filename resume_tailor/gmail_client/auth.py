import os
import json
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from resume_tailor.config import GMAIL_CREDENTIALS_PATH, GMAIL_TOKEN_PATH

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def get_gmail_service():
    """Get an authenticated Gmail API service.

    On first run, prompts for manual OAuth code entry and caches the token.
    On subsequent runs, auto-refreshes the cached token.

    Returns:
        Authorized Gmail service object
    """
    creds = None

    if GMAIL_TOKEN_PATH.exists():
        try:
            creds = Credentials.from_authorized_user_file(GMAIL_TOKEN_PATH, SCOPES)
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
        except Exception:
            creds = None

    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(
            GMAIL_CREDENTIALS_PATH,
            SCOPES,
            redirect_uri='http://localhost/',
        )

        # Manual OAuth flow for headless/WSL2 environments
        auth_url, _ = flow.authorization_url(prompt='consent')
        print("\n" + "="*70)
        print("🔐 GOOGLE AUTHORIZATION REQUIRED")
        print("="*70)
        print("\n1️⃣  Copy this URL and paste into your WINDOWS browser:")
        print(f"\n   {auth_url}\n")
        print("2️⃣  Log in with your Gmail account and click 'Allow'")
        print("3️⃣  You'll be redirected to localhost (will show error)")
        print("4️⃣  Copy the 'code' parameter from the URL in the address bar")
        print("   Example: http://localhost/?code=XXXXXXXXXXXX...")
        print("           Copy everything after 'code='")
        print("\n5️⃣  Paste the code here: ")
        print("="*70)

        code = input("Authorization code: ").strip()
        flow.fetch_token(code=code)
        creds = flow.credentials

    if creds:
        GMAIL_TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(GMAIL_TOKEN_PATH, 'w') as f:
            f.write(creds.to_json())

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

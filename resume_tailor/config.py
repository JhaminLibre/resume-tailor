import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "output"
TEMPLATES_DIR = PROJECT_ROOT / "resume_tailor" / "rendering" / "templates"

DATA_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    raise ValueError("ANTHROPIC_API_KEY not set in environment or .env file")

MATCH_THRESHOLD = int(os.getenv("MATCH_THRESHOLD", "70"))
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

DB_PATH = DATA_DIR / "state.db"
MASTER_RESUME_PATH = DATA_DIR / "master_resume.json"
GMAIL_CREDENTIALS_PATH = DATA_DIR / "gmail_credentials.json"
GMAIL_TOKEN_PATH = DATA_DIR / "gmail_token.json"

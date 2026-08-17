import requests
import trafilatura
from resume_tailor.config import DEBUG


def fetch_linkedin_jd(linkedin_url: str, timeout: int = 10) -> str | None:
    """Fetch and extract the full job description from a LinkedIn job URL.

    Uses trafilatura to strip boilerplate and extract main content from the page.

    Args:
        linkedin_url: The LinkedIn job posting URL
        timeout: Request timeout in seconds

    Returns:
        Extracted job description text, or None if fetch/extraction fails
    """
    if DEBUG:
        print(f"[DEBUG] Fetching LinkedIn JD from {linkedin_url}")

    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            )
        }

        response = requests.get(linkedin_url, headers=headers, timeout=timeout)
        response.raise_for_status()

        extracted = trafilatura.extract(
            response.text,
            include_comments=False,
            favor_precision=True,
        )

        if not extracted:
            if DEBUG:
                print(f"[DEBUG] trafilatura returned empty for {linkedin_url}")
            return None

        extracted = extracted.strip()

        if len(extracted) < 100:
            if DEBUG:
                print(
                    f"[DEBUG] Extracted text too short ({len(extracted)} chars), "
                    "possibly truncated/behind login wall"
                )
            return None

        if any(
            keyword in extracted.lower()
            for keyword in ["sign in", "log in", "create account", "verify identity"]
        ):
            if DEBUG:
                print(f"[DEBUG] Login wall detected in {linkedin_url}")
            return None

        return extracted

    except requests.RequestException as e:
        if DEBUG:
            print(f"[DEBUG] Request failed for {linkedin_url}: {e}")
        return None
    except Exception as e:
        if DEBUG:
            print(f"[DEBUG] Unexpected error fetching {linkedin_url}: {e}")
        return None

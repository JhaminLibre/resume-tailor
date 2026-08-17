import re
import requests
import trafilatura
from ddgs import DDGS
from resume_tailor.config import DEBUG

KNOWN_ATS_DOMAINS = [
    "greenhouse.io",
    "lever.co",
    "workday.com",
    "ashby.com",
    "smartrecruiters.com",
    "icims.com",
    "jobvite.com",
    "bamboohr.com",
]


def search_company_careers_url(company_name: str, job_title: str, timeout: int = 5) -> str | None:
    """Search for a company's careers page or ATS listing using DuckDuckGo.

    Args:
        company_name: Company name
        job_title: Job title to search for
        timeout: Search timeout in seconds

    Returns:
        URL to a careers page or job listing, or None if not found
    """
    if DEBUG:
        print(f"[DEBUG] Searching for {company_name} careers page for {job_title}")

    try:
        ddgs = DDGS()
        query = f'"{company_name}" careers {job_title} site:({" OR site:".join(KNOWN_ATS_DOMAINS)})'

        results = ddgs.text(query, max_results=5, timelimit="y")

        if not results:
            if DEBUG:
                print(f"[DEBUG] No ATS results for {company_name}, trying company site search")
            query = f'"{company_name}" careers {job_title}'
            results = ddgs.text(query, max_results=3, timelimit="y")

        if results:
            top_url = results[0]["href"]
            if DEBUG:
                print(f"[DEBUG] Found careers URL: {top_url}")
            return top_url

        return None

    except Exception as e:
        if DEBUG:
            print(f"[DEBUG] Search failed for {company_name}: {e}")
        return None


def fetch_company_site_jd(
    company_name: str, job_title: str, timeout: int = 10
) -> str | None:
    """Search for and fetch a job description from a company's careers page.

    Args:
        company_name: Company name
        job_title: Job title
        timeout: Request timeout in seconds

    Returns:
        Extracted job description text, or None if not found
    """
    careers_url = search_company_careers_url(company_name, job_title, timeout=5)

    if not careers_url:
        if DEBUG:
            print(f"[DEBUG] No careers URL found for {company_name}")
        return None

    if DEBUG:
        print(f"[DEBUG] Fetching company site JD from {careers_url}")

    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            )
        }

        response = requests.get(careers_url, headers=headers, timeout=timeout)
        response.raise_for_status()

        extracted = trafilatura.extract(
            response.text,
            include_comments=False,
            favor_precision=True,
        )

        if not extracted:
            if DEBUG:
                print(f"[DEBUG] trafilatura returned empty for {careers_url}")
            return None

        extracted = extracted.strip()

        if len(extracted) < 100:
            if DEBUG:
                print(f"[DEBUG] Extracted text too short ({len(extracted)} chars)")
            return None

        return extracted

    except requests.RequestException as e:
        if DEBUG:
            print(f"[DEBUG] Request failed for {careers_url}: {e}")
        return None
    except Exception as e:
        if DEBUG:
            print(f"[DEBUG] Unexpected error fetching company site: {e}")
        return None

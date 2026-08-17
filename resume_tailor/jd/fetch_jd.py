import sqlite3
from resume_tailor.jd.fetch_linkedin import fetch_linkedin_jd
from resume_tailor.jd.fetch_company_site import fetch_company_site_jd
from resume_tailor.config import DB_PATH, DEBUG


def resolve_job_description(
    job_id: int, linkedin_url: str, company_name: str, job_title: str, snippet: str
) -> tuple[str | None, str]:
    """Resolve a job description using a tiered fallback strategy.

    Tries in order:
    1. Fetch full description from LinkedIn URL
    2. Search for company careers page and fetch from there
    3. Fall back to snippet with a caveat

    Args:
        job_id: Job ID (for DB update)
        linkedin_url: LinkedIn job URL
        company_name: Company name (for fallback search)
        job_title: Job title (for fallback search)
        snippet: Email snippet (last resort)

    Returns:
        Tuple of (full_description_text, source) where source is one of:
        'linkedin_fetch', 'company_site_fetch', 'snippet_only'
    """
    if DEBUG:
        print(f"[DEBUG] Resolving JD for {company_name} - {job_title}")

    full_description = fetch_linkedin_jd(linkedin_url)
    if full_description:
        if DEBUG:
            print(f"[DEBUG] Successfully fetched from LinkedIn")
        update_job_description(job_id, full_description, "linkedin_fetch")
        return full_description, "linkedin_fetch"

    if DEBUG:
        print(f"[DEBUG] LinkedIn fetch failed, trying company site search")

    full_description = fetch_company_site_jd(company_name, job_title)
    if full_description:
        if DEBUG:
            print(f"[DEBUG] Successfully fetched from company site")
        update_job_description(job_id, full_description, "company_site_fetch")
        return full_description, "company_site_fetch"

    if DEBUG:
        print(f"[DEBUG] Company site fetch failed, falling back to snippet")

    caveat = (
        "\n\n[CAVEAT: This evaluation is based on a limited job snippet from the email, "
        "not the full job description. The score and reasoning may not be fully accurate. "
        "Use 'resume-tailor set-jd' to manually provide the full description.]"
    )
    snippet_with_caveat = snippet + caveat if snippet else caveat

    update_job_description(job_id, snippet_with_caveat, "snippet_only")
    return snippet_with_caveat, "snippet_only"


def update_job_description(job_id: int, full_description: str, source: str):
    """Update a job's full description and source in the database.

    Args:
        job_id: Job ID
        full_description: The full job description text
        source: Source of the description ('linkedin_fetch', 'company_site_fetch', or 'snippet_only')
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        """
    UPDATE jobs
    SET full_description = ?, full_description_source = ?, updated_at = datetime('now')
    WHERE job_id = ?
    """,
        (full_description, source, job_id),
    )

    conn.commit()
    conn.close()


def set_manual_jd(job_id: int, full_description: str):
    """Manually set a job description (user-provided via CLI).

    Args:
        job_id: Job ID
        full_description: The full job description text provided by the user
    """
    update_job_description(job_id, full_description, "manual_paste")

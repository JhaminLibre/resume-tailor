import sqlite3
from datetime import datetime
from resume_tailor.db import init_db, insert_company, insert_job
from resume_tailor.gmail_client.fetch import fetch_linkedin_alerts
from resume_tailor.gmail_client.parse_alert import parse_linkedin_alert_html
from resume_tailor.config import DB_PATH


def is_email_processed(gmail_message_id: str) -> bool:
    """Check if an email has already been processed."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM emails_processed WHERE gmail_message_id = ?", (gmail_message_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None


def mark_email_processed(gmail_message_id: str, received_at: str, num_jobs: int):
    """Mark an email as processed."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
    INSERT OR IGNORE INTO emails_processed (gmail_message_id, received_at, jobs_extracted)
    VALUES (?, ?, ?)
    """,
        (gmail_message_id, received_at, num_jobs),
    )
    conn.commit()
    conn.close()


def job_exists(linkedin_url: str) -> bool:
    """Check if a job already exists by its normalized LinkedIn URL."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM jobs WHERE linkedin_url = ?", (linkedin_url,))
    result = cursor.fetchone()
    conn.close()
    return result is not None


def fetch_and_process_alerts(debug_mode: bool = False) -> dict:
    """Fetch LinkedIn job alerts from Gmail and insert new jobs into the database.

    Args:
        debug_mode: If True, parse emails but don't save to database (useful for testing)

    Returns:
        Summary dict with keys: emails_fetched, jobs_found, jobs_new, jobs_skipped, errors
    """
    init_db()

    summary = {
        "emails_fetched": 0,
        "jobs_found": 0,
        "jobs_new": 0,
        "jobs_skipped": 0,
        "errors": [],
    }

    if debug_mode:
        print("\n🔧 DEBUG MODE: Parsing emails but NOT saving to database\n")

    try:
        emails = fetch_linkedin_alerts(max_results=10)
    except Exception as e:
        summary["errors"].append(f"Failed to fetch Gmail alerts: {e}")
        return summary

    summary["emails_fetched"] = len(emails)

    for email in emails:
        email_id = email["id"]

        if not debug_mode and is_email_processed(email_id):
            continue

        try:
            jobs = parse_linkedin_alert_html(email["body_html"])
            summary["jobs_found"] += len(jobs)

            for job in jobs:
                if not debug_mode and job_exists(job.linkedin_url):
                    print(f"  [SKIPPED] Duplicate: {job.title} @ {job.company}")
                    summary["jobs_skipped"] += 1
                    continue

                try:
                    if not debug_mode:
                        company_id = insert_company(job.company, location=job.location)

                        job_id = insert_job(
                            job_title=job.title,
                            company_id=company_id,
                            linkedin_url=job.linkedin_url,
                            snippet=job.snippet,
                            date_found=email["received_at"],
                            location=job.location,
                        )
                        print(f"  [INSERTED] {job.title} @ {job.company}")

                    summary["jobs_new"] += 1

                except Exception as e:
                    print(f"  [ERROR] {job.title} @ {job.company}: {e}")
                    summary["errors"].append(
                        f"Failed to insert job {job.title} @ {job.company}: {e}"
                    )

            if not debug_mode:
                mark_email_processed(email_id, email["received_at"], len(jobs))

        except Exception as e:
            summary["errors"].append(f"Failed to parse email {email_id}: {e}")

    return summary

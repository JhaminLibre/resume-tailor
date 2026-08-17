"""Bridge between resume-tailor DB and job-search-analytics skill."""

import sqlite3
import json
from pathlib import Path
from resume_tailor.config import DB_PATH, OUTPUT_DIR


def get_new_jobs() -> list[dict]:
    """Get NEW/UNAPPLIED jobs from resume-tailor DB for skill evaluation.

    Returns jobs that need to be evaluated and tailored.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            j.job_id,
            j.job_title,
            c.company_name,
            j.full_description,
            j.linkedin_url,
            j.location
        FROM jobs j
        JOIN companies c ON j.company_id = c.company_id
        LEFT JOIN applications a ON j.job_id = a.job_id
        WHERE (a.application_id IS NULL OR a.application_status = 'not_applied')
        ORDER BY j.date_added DESC
    """)

    jobs = []
    for job_id, title, company, description, url, location in cursor.fetchall():
        jobs.append(
            {
                "job_id": job_id,
                "title": title,
                "company": company,
                "description": description or "",
                "url": url,
                "location": location or "Remote",
            }
        )

    conn.close()
    return jobs


def mark_job_applied(job_id: int, resume_path: str | None = None) -> None:
    """Mark a job as applied in the resume-tailor DB.

    Args:
        job_id: The job_id from resume-tailor DB
        resume_path: Optional path to the tailored resume PDF
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE applications
        SET application_status = 'applied', updated_at = datetime('now')
        WHERE job_id = ?
        """,
        (job_id,),
    )

    if cursor.rowcount == 0:
        # No application record, create one
        cursor.execute(
            """
            INSERT INTO applications (job_id, application_status, created_at, updated_at)
            VALUES (?, 'applied', datetime('now'), datetime('now'))
            """,
            (job_id,),
        )

    conn.commit()
    conn.close()


def export_jobs_for_skill(output_file: str | None = None) -> str:
    """Export new jobs to JSON for skill to process.

    Args:
        output_file: Optional path to save JSON. Defaults to scratchpad.

    Returns:
        Path to exported JSON file
    """
    if output_file is None:
        output_file = str(Path.home() / ".claude" / "resume-tailor-jobs.json")

    jobs = get_new_jobs()

    with open(output_file, "w") as f:
        json.dump(
            {
                "jobs": jobs,
                "count": len(jobs),
                "source": "resume-tailor database",
            },
            f,
            indent=2,
        )

    return output_file


def get_tailored_resume_path(job_id: int) -> str | None:
    """Get the path to a tailored resume PDF for a job.

    Args:
        job_id: The job_id

    Returns:
        Path to PDF if it exists, None otherwise
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT r.file
        FROM resumes r
        WHERE r.job_id = ? AND r.resume_type = 'tailored'
        ORDER BY r.created_at DESC
        LIMIT 1
        """,
        (job_id,),
    )

    result = cursor.fetchone()
    conn.close()

    return result[0] if result else None

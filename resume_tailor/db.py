import sqlite3
import json
from pathlib import Path
from datetime import datetime
from resume_tailor.config import DB_PATH
from resume_tailor.models import Resume, MatchResult


def init_db():
    """Initialize the SQLite database with all tables."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("PRAGMA foreign_keys = ON")

    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS emails_processed (
        gmail_message_id TEXT PRIMARY KEY,
        received_at TEXT NOT NULL,
        processed_at TEXT NOT NULL DEFAULT (datetime('now')),
        jobs_extracted INTEGER NOT NULL DEFAULT 0
    )
    """
    )

    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS companies (
        company_id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_name TEXT NOT NULL UNIQUE,
        industry TEXT,
        location TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """
    )

    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS jobs (
        job_id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_title TEXT NOT NULL,
        company_id INTEGER NOT NULL REFERENCES companies(company_id),
        location TEXT,
        linkedin_url TEXT NOT NULL UNIQUE,
        snippet TEXT,
        full_description TEXT,
        full_description_source TEXT NOT NULL DEFAULT 'snippet_only'
            CHECK (full_description_source IN ('linkedin_fetch','company_site_fetch','snippet_only','manual_paste')),
        date_found TEXT NOT NULL,
        date_added TEXT NOT NULL DEFAULT (datetime('now')),
        status TEXT NOT NULL DEFAULT 'new'
            CHECK (status IN ('new','evaluated','tailored','skipped','error')),
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """
    )

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)")

    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS evaluations (
        evaluation_id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER NOT NULL REFERENCES jobs(job_id),
        match_score INTEGER NOT NULL CHECK (match_score BETWEEN 0 AND 100),
        match_reasoning TEXT NOT NULL,
        model_used TEXT,
        evaluated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """
    )

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_evaluations_job ON evaluations(job_id)")

    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS resumes (
        resume_id INTEGER PRIMARY KEY AUTOINCREMENT,
        resume_name TEXT NOT NULL,
        resume_type TEXT NOT NULL CHECK (resume_type IN ('master','tailored')),
        role TEXT CHECK (role IN ('strategy-analytics', 'pm', 'analytics-engineer', NULL)),
        job_id INTEGER REFERENCES jobs(job_id),
        content_json TEXT NOT NULL,
        file TEXT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        CHECK ( (resume_type='master' AND job_id IS NULL)
             OR (resume_type='tailored' AND job_id IS NOT NULL) )
    )
    """
    )

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_resumes_job ON resumes(job_id)")

    cursor.execute(
        """
    CREATE TABLE IF NOT EXISTS applications (
        application_id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER NOT NULL UNIQUE REFERENCES jobs(job_id),
        resume_id INTEGER REFERENCES resumes(resume_id),
        applied_at TEXT,
        application_status TEXT NOT NULL DEFAULT 'not_applied'
            CHECK (application_status IN ('not_applied','applied','interviewing','rejected','offer','accepted')),
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """
    )

    conn.commit()
    conn.close()


def insert_master_resume(resume: Resume, source_files: list[str], role: str | None = None) -> int:
    """Insert a master resume into the database.

    Args:
        resume: Resume object
        source_files: List of source file paths used to create the resume
        role: Optional role tag ('strategy-analytics', 'pm', 'data-engineer')

    Returns:
        The resume_id of the inserted resume
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    content_json = resume.model_dump_json()

    cursor.execute(
        """
    INSERT INTO resumes (resume_name, resume_type, role, job_id, content_json, created_at)
    VALUES (?, ?, ?, ?, ?, datetime('now'))
    """,
        ("master", "master", role, None, content_json),
    )

    resume_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return resume_id


def get_master_resume() -> Resume | None:
    """Retrieve the master resume from the database.

    Returns:
        Resume object if found, None otherwise
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        """
    SELECT content_json FROM resumes
    WHERE resume_type = 'master'
    ORDER BY created_at DESC
    LIMIT 1
    """
    )

    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    resume_dict = json.loads(row[0])
    return Resume(**resume_dict)


def get_master_resume_by_role(role: str) -> Resume | None:
    """Retrieve a master resume by role.

    Args:
        role: Role tag ('strategy-analytics', 'pm', 'data-engineer')

    Returns:
        Resume object if found, None otherwise
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        """
    SELECT content_json FROM resumes
    WHERE resume_type = 'master' AND role = ?
    ORDER BY created_at DESC
    LIMIT 1
    """,
        (role,),
    )

    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    resume_dict = json.loads(row[0])
    return Resume(**resume_dict)


def insert_company(name: str, industry: str | None = None, location: str | None = None) -> int:
    """Insert or get a company.

    Args:
        name: Company name
        industry: Industry (optional)
        location: Location (optional)

    Returns:
        The company_id
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        """
    INSERT OR IGNORE INTO companies (company_name, industry, location)
    VALUES (?, ?, ?)
    """,
        (name, industry, location),
    )

    cursor.execute("SELECT company_id FROM companies WHERE company_name = ?", (name,))
    company_id = cursor.fetchone()[0]

    conn.commit()
    conn.close()

    return company_id


def insert_job(
    job_title: str,
    company_id: int,
    linkedin_url: str,
    snippet: str,
    date_found: str,
    location: str | None = None,
) -> int:
    """Insert a job into the database.

    Args:
        job_title: Job title
        company_id: Company ID (foreign key)
        linkedin_url: LinkedIn job URL (must be unique/normalized)
        snippet: Job snippet from email
        date_found: Date the job was found (ISO8601)
        location: Job location (optional)

    Returns:
        The job_id of the inserted job
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        """
    INSERT INTO jobs (job_title, company_id, location, linkedin_url, snippet, date_found)
    VALUES (?, ?, ?, ?, ?, ?)
    """,
        (job_title, company_id, location, linkedin_url, snippet, date_found),
    )

    job_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return job_id


def insert_evaluation(job_id: int, match_result: MatchResult, model_used: str = "claude-opus-5") -> int:
    """Insert a job evaluation.

    Args:
        job_id: Job ID (foreign key)
        match_result: MatchResult object with score and reasoning
        model_used: Model name used for evaluation

    Returns:
        The evaluation_id
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    match_reasoning = json.dumps({
        "summary": match_result.summary,
        "strengths": match_result.strengths,
        "gaps": match_result.gaps,
    })

    cursor.execute(
        """
    INSERT INTO evaluations (job_id, match_score, match_reasoning, model_used)
    VALUES (?, ?, ?, ?)
    """,
        (job_id, match_result.match_score, match_reasoning, model_used),
    )

    evaluation_id = cursor.lastrowid

    cursor.execute(
        "UPDATE jobs SET status = 'evaluated', updated_at = datetime('now') WHERE job_id = ?",
        (job_id,),
    )

    conn.commit()
    conn.close()

    return evaluation_id


def get_job_by_id(job_id: int) -> dict | None:
    """Retrieve a job by ID.

    Args:
        job_id: Job ID

    Returns:
        Job dict or None if not found
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        """
    SELECT job_id, job_title, company_id, linkedin_url, full_description, full_description_source
    FROM jobs WHERE job_id = ?
    """,
        (job_id,),
    )

    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    return {
        "job_id": row[0],
        "job_title": row[1],
        "company_id": row[2],
        "linkedin_url": row[3],
        "full_description": row[4],
        "full_description_source": row[5],
    }


def insert_tailored_resume(job_id: int, resume: Resume, pdf_path: str | None = None) -> int:
    """Insert a tailored resume for a job.

    Args:
        job_id: Job ID (foreign key)
        resume: Resume object (tailored version)
        pdf_path: Path to the rendered PDF (optional)

    Returns:
        The resume_id
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT job_title, company_id FROM jobs WHERE job_id = ?", (job_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise ValueError(f"Job {job_id} not found")

    job_title, company_id = row

    cursor.execute("SELECT company_name FROM companies WHERE company_id = ?", (company_id,))
    company_name = cursor.fetchone()[0]

    resume_name = f"{company_name} - {job_title}"
    content_json = resume.model_dump_json()

    cursor.execute(
        """
    INSERT INTO resumes (resume_name, resume_type, job_id, content_json, file)
    VALUES (?, ?, ?, ?, ?)
    """,
        (resume_name, "tailored", job_id, content_json, pdf_path),
    )

    resume_id = cursor.lastrowid

    cursor.execute(
        "UPDATE jobs SET status = 'tailored', updated_at = datetime('now') WHERE job_id = ?",
        (job_id,),
    )

    cursor.execute(
        "INSERT OR IGNORE INTO applications (job_id, resume_id, application_status) VALUES (?, ?, 'not_applied')",
        (job_id, resume_id),
    )

    conn.commit()
    conn.close()

    return resume_id

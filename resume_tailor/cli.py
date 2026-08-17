import json
import click
from pathlib import Path
from resume_tailor.db import init_db, insert_master_resume, get_master_resume
from resume_tailor.importer.extract_text import extract_text
from resume_tailor.importer.structure_resume import structure_resume_with_claude
from resume_tailor.config import MASTER_RESUME_PATH


@click.group()
def cli():
    """resume-tailor: Auto-tailor resumes to job postings from LinkedIn job alerts."""
    pass


@cli.command()
@click.argument("resume_file", type=click.Path(exists=True))
def import_resume(resume_file: str):
    """Import and structure a resume from a PDF or DOCX file.

    Extracts text, uses Claude to structure it, and asks for your review before saving.
    """
    click.echo(f"📄 Importing resume from: {resume_file}")

    try:
        click.echo("Extracting text...")
        raw_text = extract_text(resume_file)
        click.echo(f"✓ Extracted {len(raw_text)} characters")

        click.echo("Structuring resume with Claude...")
        resume = structure_resume_with_claude(raw_text)
        click.echo("✓ Successfully structured resume")

        click.echo("\n" + "=" * 80)
        click.echo("REVIEW YOUR STRUCTURED RESUME")
        click.echo("=" * 80)
        click.echo(json.dumps(resume.model_dump(), indent=2))
        click.echo("=" * 80 + "\n")

        if click.confirm("Does this look correct? Save to database?"):
            init_db()
            source_files = [str(Path(resume_file).resolve())]
            resume_id = insert_master_resume(resume, source_files)
            click.echo(f"✓ Master resume saved (ID: {resume_id})")
            click.echo(f"📁 Resume JSON can be edited at: {MASTER_RESUME_PATH}")
        else:
            click.echo("Cancelled. Resume not saved.")

    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        raise click.Abort()


@cli.command()
def list_resumes():
    """List all stored resumes (master + tailored)."""
    init_db()
    master = get_master_resume()
    if master:
        click.echo("📋 Master Resume:")
        click.echo(f"  Name: {master.contact.full_name}")
        click.echo(f"  Email: {master.contact.email}")
        click.echo(f"  Experience: {len(master.experience)} roles")
        click.echo(f"  Skills: {len(master.skills)} categories")
    else:
        click.echo("⚠️  No master resume found. Run 'import-resume' first.")


@cli.command()
def list_applications():
    """List all tailored resumes with their job details."""
    import sqlite3
    from resume_tailor.config import DB_PATH

    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            r.file,
            j.job_title,
            j.company_id,
            j.linkedin_url,
            e.match_score,
            c.company_name,
            a.application_status
        FROM resumes r
        JOIN applications a ON r.resume_id = a.resume_id
        JOIN jobs j ON a.job_id = j.job_id
        JOIN companies c ON j.company_id = c.company_id
        LEFT JOIN evaluations e ON j.job_id = e.job_id
        WHERE r.resume_type = 'tailored'
        ORDER BY r.created_at DESC
    """)

    rows = cursor.fetchall()
    conn.close()

    if not rows:
        click.echo("No tailored resumes found.")
        return

    click.echo("📄 Tailored Resumes:")
    for file, job_title, company_id, linkedin_url, match_score, company_name, status in rows:
        click.echo(f"\n  📄 {Path(file).name}")
        click.echo(f"     Job: {job_title} @ {company_name}")
        click.echo(f"     Score: {match_score}/100")
        click.echo(f"     Status: {status}")
        click.echo(f"     URL: {linkedin_url}")


@cli.command()
def active_applications():
    """List applications in progress (not rejected/accepted)."""
    import sqlite3
    from resume_tailor.config import DB_PATH

    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            a.job_id,
            r.file,
            j.job_title,
            j.linkedin_url,
            e.match_score,
            c.company_name,
            a.application_status
        FROM applications a
        JOIN resumes r ON a.resume_id = r.resume_id
        JOIN jobs j ON a.job_id = j.job_id
        JOIN companies c ON j.company_id = c.company_id
        LEFT JOIN evaluations e ON j.job_id = e.job_id
        WHERE a.application_status IN ('not_applied', 'applied', 'interviewing', 'offer')
        ORDER BY r.created_at DESC
    """)

    rows = cursor.fetchall()
    conn.close()

    if not rows:
        click.echo("No active applications.")
        return

    click.echo("📋 Active Applications (in progress):")
    for job_id, file, job_title, linkedin_url, match_score, company_name, status in rows:
        click.echo(f"\n  📄 {Path(file).name}")
        click.echo(f"     Job: {job_title} @ {company_name}")
        click.echo(f"     Score: {match_score}/100")
        click.echo(f"     Status: {status}")
        click.echo(f"     URL: {linkedin_url}")
        click.echo(f"     📂 Open: resume-tailor open-resume {job_id}")


@cli.command()
@click.argument("job_id", type=int)
def open_resume(job_id: int):
    """Open a resume file in Windows Explorer."""
    import sqlite3
    import os
    import platform
    from resume_tailor.config import DB_PATH

    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT r.file
        FROM resumes r
        JOIN applications a ON r.resume_id = a.resume_id
        WHERE a.job_id = ? AND r.resume_type = 'tailored'
        LIMIT 1
    """, (job_id,))

    result = cursor.fetchone()
    conn.close()

    if not result:
        click.echo(f"❌ No tailored resume found for job {job_id}")
        return

    file_path = result[0]
    if not Path(file_path).exists():
        click.echo(f"❌ Resume file not found: {file_path}")
        return

    system = platform.system()
    if system == "Windows":
        os.startfile(file_path)
    elif system == "Darwin":
        os.system(f'open "{file_path}"')
    else:
        try:
            import subprocess
            file_path_str = str(Path(file_path))
            if file_path_str.startswith("/"):
                windows_path = f"\\\\wsl$\\Ubuntu\\{file_path_str[1:].replace('/', chr(92))}"
            else:
                windows_path = file_path_str
            subprocess.run(["explorer.exe", "/select", windows_path], check=False)
            click.echo(f"✅ Opened in Windows Explorer: {Path(file_path).name}")
        except Exception as e:
            click.echo(f"❌ Failed to open file: {e}")


@cli.command()
@click.option(
    "--threshold",
    type=int,
    default=None,
    help="Match score threshold (0-100). Only scores >= threshold get tailored (default: 70)",
)
@click.option(
    "--debug",
    is_flag=True,
    help="Debug mode: parse emails but don't save to database",
)
def check(threshold: int, debug: bool):
    """Check for new LinkedIn job alerts and process them.

    Fetches LinkedIn job-alert emails, evaluates each job against your master resume,
    and generates tailored PDFs for jobs meeting the match threshold.
    """
    from resume_tailor.config import MATCH_THRESHOLD
    from resume_tailor.pipeline import fetch_and_process_alerts
    from resume_tailor.jd.fetch_jd import resolve_job_description
    from resume_tailor.matching.evaluate import evaluate_job_match
    from resume_tailor.tailoring.tailor import tailor_resume_to_job
    from resume_tailor.rendering.render_pdf import render_resume_to_pdf
    from resume_tailor.db import (
        get_master_resume,
        get_job_by_id,
        insert_evaluation,
        insert_tailored_resume,
    )
    import sqlite3
    from resume_tailor.config import DB_PATH

    if threshold is None:
        threshold = MATCH_THRESHOLD

    click.echo("🔄 Checking for new LinkedIn job alerts...")

    init_db()

    master_resume = get_master_resume()
    if not master_resume:
        click.echo("❌ No master resume found. Run 'resume-tailor import-resume' first.")
        raise click.Abort()

    summary = fetch_and_process_alerts(debug_mode=debug)
    click.echo(f"✓ Fetched {summary['emails_fetched']} emails, found {summary['jobs_found']} jobs")
    if summary["errors"]:
        for error in summary["errors"]:
            click.echo(f"  ⚠️  {error}")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT job_id FROM jobs WHERE status = 'new'")
    new_jobs = cursor.fetchall()
    conn.close()

    click.echo(f"\n📋 Processing {len(new_jobs)} new jobs...")

    evaluated = 0
    tailored = 0
    skipped_low_score = 0

    for (job_id,) in new_jobs:
        job = get_job_by_id(job_id)
        if not job:
            continue

        try:
            click.echo(f"\n  📌 {job['job_title']} @ {job['company_id']}")

            if not job["full_description"]:
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute("SELECT company_name FROM companies WHERE company_id = ?", (job["company_id"],))
                company_name = cursor.fetchone()[0]
                conn.close()

                click.echo("    Fetching full job description...")
                description, source = resolve_job_description(
                    job_id,
                    job["linkedin_url"],
                    company_name,
                    job["job_title"],
                    "",
                )
            else:
                description = job["full_description"]

            click.echo("    Evaluating match...")
            match_result = evaluate_job_match(master_resume, job["job_title"], description)
            insert_evaluation(job_id, match_result)
            evaluated += 1

            click.echo(f"    Score: {match_result.match_score}/100")

            if match_result.match_score >= threshold:
                click.echo("    ✨ Above threshold! Tailoring resume...")
                tailored_resume = tailor_resume_to_job(master_resume, job["job_title"], description)

                click.echo("    Rendering PDF...")
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute("SELECT company_name FROM companies WHERE company_id = ?", (job["company_id"],))
                company_name = cursor.fetchone()[0]
                conn.close()

                pdf_path = render_resume_to_pdf(tailored_resume, company_name, job["job_title"])
                insert_tailored_resume(job_id, tailored_resume, pdf_path)
                tailored += 1
                click.echo(f"    ✅ PDF saved: {pdf_path}")
            else:
                click.echo(f"    Score {match_result.match_score} < threshold {threshold}, skipping")
                skipped_low_score += 1

        except Exception as e:
            click.echo(f"    ❌ Error: {e}")

    click.echo(f"\n{'='*60}")
    click.echo(f"Summary:")
    click.echo(f"  Emails fetched: {summary['emails_fetched']}")
    click.echo(f"  New jobs: {summary['jobs_new']}")
    click.echo(f"  Evaluated: {evaluated}")
    click.echo(f"  Tailored: {tailored}")
    click.echo(f"  Skipped (low score): {skipped_low_score}")
    if summary["errors"]:
        click.echo(f"  Errors: {len(summary['errors'])}")


def main():
    """Entry point for the resume-tailor CLI."""
    cli()


if __name__ == "__main__":
    main()

import json
import click
from pathlib import Path
from resume_tailor.db import init_db, insert_master_resume, get_master_resume, get_master_resume_by_role
from resume_tailor.importer.extract_text import extract_text
from resume_tailor.importer.structure_resume import structure_resume_with_claude
from resume_tailor.config import MASTER_RESUME_PATH


@click.group()
def cli():
    """resume-tailor: Auto-tailor resumes to job postings from LinkedIn job alerts."""
    pass


@cli.command()
@click.argument("resume_file", type=click.Path(exists=True))
@click.option(
    "--role",
    type=click.Choice(["strategy-analytics", "pm", "analytics-engineer"]),
    default=None,
    help="Role tag for this master resume (optional)",
)
def import_resume(resume_file: str, role: str | None):
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
            resume_id = insert_master_resume(resume, source_files, role=role)
            role_label = f" ({role})" if role else ""
            click.echo(f"✓ Master resume saved{role_label} (ID: {resume_id})")
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
        LEFT JOIN evaluations e ON j.job_id = e.job_id AND e.evaluation_id = (
            SELECT evaluation_id FROM evaluations WHERE job_id = j.job_id ORDER BY evaluated_at DESC LIMIT 1
        )
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
def mark_applied(job_id: int):
    """Mark an application as applied."""
    import sqlite3
    from resume_tailor.config import DB_PATH

    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE applications
        SET application_status = 'applied', updated_at = datetime('now')
        WHERE job_id = ?
    """, (job_id,))

    if cursor.rowcount == 0:
        click.echo(f"❌ Application not found for job {job_id}")
    else:
        click.echo(f"✅ Marked job {job_id} as applied")

    conn.commit()
    conn.close()


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
    try:
        if system == "Windows":
            os.startfile(file_path)
            click.echo(f"✅ Opened: {Path(file_path).name}")
        elif system == "Darwin":
            os.system(f'open "{file_path}"')
            click.echo(f"✅ Opened: {Path(file_path).name}")
        else:
            import subprocess
            file_path_abs = str(Path(file_path).resolve())
            windows_path = f"\\\\wsl$\\Ubuntu{file_path_abs.replace('/', chr(92))}"
            subprocess.Popen(["powershell.exe", "-Command", f"explorer.exe /select,'{windows_path}'"])
            click.echo(f"✅ Opened in Windows Explorer: {Path(file_path).name}")
    except Exception as e:
        click.echo(f"❌ Failed to open file: {e}")


@cli.command()
@click.option(
    "--debug",
    is_flag=True,
    help="Debug mode: parse emails but don't save to database",
)
def check(debug: bool):
    """Check for new LinkedIn job alerts.

    Fetches LinkedIn job-alert emails and saves them to the database.
    Use the job-search-analytics skill to score and tailor resumes.
    """
    from resume_tailor.pipeline import fetch_and_process_alerts

    click.echo("🔄 Checking for new LinkedIn job alerts...")

    init_db()

    summary = fetch_and_process_alerts(debug_mode=debug)
    click.echo(f"✓ Fetched {summary['emails_fetched']} emails, found {summary['jobs_found']} jobs")
    if summary["errors"]:
        for error in summary["errors"]:
            click.echo(f"  ⚠️  {error}")

    click.echo(f"\n📊 Summary:")
    click.echo(f"  New unique jobs: {summary['jobs_new']}")
    click.echo(f"  Duplicates skipped: {summary['jobs_skipped']}")

    if summary['jobs_new'] > 0:
        click.echo(f"\n💡 Next step: Run the job-search-analytics skill to score and tailor these jobs")


@cli.command()
def evaluate_and_tailor():
    """Evaluate new jobs and tailor resumes using skill-based approach."""
    import sqlite3
    from pathlib import Path
    from resume_tailor.skill_integration import (
        read_skill_files,
        score_job_with_skill,
        generate_spec_json,
        build_resume_docx,
        convert_docx_to_pdf,
    )
    from resume_tailor.config import DB_PATH, OUTPUT_DIR

    init_db()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    click.echo("📊 Loading skill files...")
    skill_files = read_skill_files()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT job_id, job_title, full_description FROM jobs WHERE status = 'new' ORDER BY job_id"
    )
    new_jobs = cursor.fetchall()
    conn.close()

    if not new_jobs:
        click.echo("No new jobs to evaluate.")
        return

    click.echo(f"\n📋 Evaluating {len(new_jobs)} jobs...")

    tailored = 0
    strong_fits = 0
    weak_fits = 0

    for job_id, job_title, job_description in new_jobs:
        click.echo(f"\n  📌 {job_title} (Job {job_id})")

        try:
            click.echo("    Scoring...")
            score_result = score_job_with_skill(job_title, job_description, skill_files)

            tier = score_result["score_tier"]
            click.echo(f"    Tier: {tier}")
            click.echo(f"    Reasoning: {score_result['reasoning']}")

            if not score_result.get("should_tailor"):
                click.echo("    ⊘ Skipping tailoring (not recommended)")
                continue

            if tier == "Strong fit":
                strong_fits += 1
            elif tier == "Weak fit":
                weak_fits += 1

            click.echo("    Tailoring resume...")
            spec = generate_spec_json(job_title, job_description, skill_files)

            # Get company name for filename
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT company_name FROM companies WHERE company_id = (SELECT company_id FROM jobs WHERE job_id = ?)",
                (job_id,),
            )
            company_name = cursor.fetchone()[0]
            conn.close()

            from datetime import datetime

            month_year = datetime.now().strftime("%B %Y")
            filename = f"Matthew Pennisi - Resume {month_year} ({company_name})"
            docx_path = str(OUTPUT_DIR / f"{filename}.docx")
            pdf_path = str(OUTPUT_DIR / f"{filename}.pdf")

            click.echo("    Building DOCX...")
            build_resume_docx(spec, docx_path)

            click.echo("    Converting to PDF...")
            convert_docx_to_pdf(docx_path)

            click.echo(f"    ✅ Generated: {Path(docx_path).name}")

            tailored += 1

        except Exception as e:
            click.echo(f"    ❌ Error: {e}")

    click.echo(f"\n{'='*60}")
    click.echo(f"Summary:")
    click.echo(f"  Strong fits: {strong_fits}")
    click.echo(f"  Weak fits: {weak_fits}")
    click.echo(f"  Tailored: {tailored}")


def main():
    """Entry point for the resume-tailor CLI."""
    cli()


if __name__ == "__main__":
    main()

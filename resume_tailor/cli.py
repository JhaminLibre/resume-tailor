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


def main():
    """Entry point for the resume-tailor CLI."""
    cli()


if __name__ == "__main__":
    main()

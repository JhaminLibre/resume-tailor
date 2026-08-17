import re
from pathlib import Path
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML
from resume_tailor.models import Resume
from resume_tailor.config import TEMPLATES_DIR, OUTPUT_DIR, DEBUG


def slugify(text: str) -> str:
    """Convert text to a URL-safe slug for use in filenames."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text.strip('-')


def render_resume_to_pdf(
    resume: Resume, company_name: str, job_title: str, output_path: str | None = None
) -> str:
    """Render a Resume object to a PDF file.

    Args:
        resume: Resume object to render
        company_name: Company name (used for filename)
        job_title: Job title (used for filename)
        output_path: Optional custom output path; if None, generates in output/ directory

    Returns:
        Path to the generated PDF file
    """
    if DEBUG:
        print(f"[DEBUG] Rendering PDF for {company_name} - {job_title}")

    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))
    template = env.get_template("resume.html.j2")

    html_content = template.render(resume=resume)

    if output_path is None:
        date_formatted = datetime.now().strftime("%B %Y")
        filename = f"Matthew Pennisi - Resume {date_formatted} ({company_name}).pdf"
        output_path = str(OUTPUT_DIR / filename)

    if DEBUG:
        print(f"[DEBUG] Writing PDF to {output_path}")

    html_string = f"""
    <html>
        <head>
            <meta charset="UTF-8">
            <style>
                {get_css_content()}
            </style>
        </head>
        <body>
            {html_content}
        </body>
    </html>
    """

    try:
        HTML(string=html_string).write_pdf(output_path)

        if DEBUG:
            print(f"[DEBUG] PDF generated successfully: {output_path}")

        return output_path

    except Exception as e:
        raise RuntimeError(f"Failed to generate PDF: {e}")


def get_css_content() -> str:
    """Load CSS content from the resume.css template file."""
    css_path = TEMPLATES_DIR / "resume.css"

    if not css_path.exists():
        raise FileNotFoundError(f"CSS template not found: {css_path}")

    with open(css_path, "r") as f:
        return f.read()

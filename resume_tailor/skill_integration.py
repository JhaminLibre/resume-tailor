"""Integration with job-search-analytics skill for evaluation and tailoring."""

import json
import subprocess
from pathlib import Path
from anthropic import Anthropic
from resume_tailor.config import DEBUG

SKILL_DIR = Path.home() / ".claude" / "skills" / "job-search-analytics"
MASTER_RESUME_PATH = SKILL_DIR / "assets" / "resume_master.md"
SCORING_CRITERIA_PATH = SKILL_DIR / "references" / "scoring-criteria.md"
BUILD_SCRIPT_PATH = SKILL_DIR / "scripts" / "build_resume.js"


def read_skill_files() -> dict:
    """Read master resume and scoring criteria from skill."""
    if not MASTER_RESUME_PATH.exists():
        raise FileNotFoundError(f"Master resume not found: {MASTER_RESUME_PATH}")
    if not SCORING_CRITERIA_PATH.exists():
        raise FileNotFoundError(f"Scoring criteria not found: {SCORING_CRITERIA_PATH}")

    with open(MASTER_RESUME_PATH) as f:
        master_resume = f.read()
    with open(SCORING_CRITERIA_PATH) as f:
        scoring_criteria = f.read()

    return {"master_resume": master_resume, "scoring_criteria": scoring_criteria}


def score_job_with_skill(job_title: str, job_description: str, skill_files: dict) -> dict:
    """Score a job posting using the skill's criteria.

    Returns:
        {
            "score_tier": "Strong fit" | "Worth a look, flag the gap" | "Weak fit",
            "reasoning": "...",
            "key_points": {"seniority": "...", "skills": "...", ...}
        }
    """
    client = Anthropic()

    prompt = f"""You are an expert recruiter evaluating jobs for Matthew Pennisi, a strategy/analytics leader with 10+ years of experience.

MASTER RESUME (ground truth):
{skill_files['master_resume']}

SCORING CRITERIA (must follow these exactly):
{skill_files['scoring_criteria']}

JOB TO EVALUATE:
Title: {job_title}
Description:
{job_description}

Evaluate this job honestly on the 5 scoring axes. Consider Matthew's seniority (10+ years as sole analytical/product partner), verified tools (SQL, dbt, Snowflake, BigQuery, Databricks, Looker, Fivetran), and proof points (Trusted Health platform strategy, Promise customer-facing analytics, etc.).

Return a JSON response with:
{{
  "score_tier": "Strong fit" | "Worth a look, flag the gap" | "Weak fit",
  "reasoning": "2-3 sentences explaining the fit",
  "key_points": {{
    "seniority": "assessment of whether this matches 10+ years",
    "skills": "which tools match, which gaps exist",
    "hands_on_vs_strategy": "balance assessment",
    "domain": "domain fit assessment",
    "customer_facing": "if relevant, assessment of customer-facing angle"
  }},
  "should_tailor": true/false
}}

Only return JSON, no other text."""

    message = client.messages.create(
        model="claude-opus-5",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )

    response_text = ""
    for block in message.content:
        if hasattr(block, "text"):
            response_text += block.text

    try:
        result = json.loads(response_text)
        return result
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse scoring response: {e}\n\n{response_text}")


def generate_spec_json(
    job_title: str, job_description: str, skill_files: dict
) -> dict:
    """Generate spec.json for build_resume.js.

    Selects which bullets to include, reorders skills, picks summary variant.
    """
    client = Anthropic()

    prompt = f"""You are helping tailor Matthew Pennski's resume for a specific job.

MASTER RESUME (source of truth - never invent content):
{skill_files['master_resume']}

JOB TO TAILOR FOR:
Title: {job_title}
Description:
{job_description}

Generate a spec.json that:
1. Selects the appropriate summary variant (hands-on/analytics framing, strategy/PM framing, or blend)
2. Reorders the 13 skills to put the most job-relevant ones first: SQL, dbt, Snowflake, Databricks, BigQuery, Fivetran, Looker, Data Modeling, Business Intelligence, AI-Assisted Analytics Tooling, Strategic Analysis, Opportunity Sizing, Cross-Functional Partnership
3. For each of the 6 roles in master resume, reorders bullets to emphasize the most relevant ones first (never drops bullets, never adds new ones)
4. Includes exact education from master resume

The spec must preserve ALL roles and ALL bullets - only reorder for relevance. Return ONLY valid JSON matching this shape:

{{
  "summary": "one of the three summary variants from master resume, adapted",
  "skills": "SQL • dbt • Snowflake • ...",
  "roles": [
    {{
      "title": "...",
      "company": "...",
      "location": "...",
      "dates": "...",
      "subtitle": "...",
      "bullets": ["bullet 1", "bullet 2", ...]
    }},
    ...
  ],
  "education": ["University of Tokyo | Master of Engineering in Material Engineering | 2011", "Colgate University | BA Physics, cum laude | 2009"]
}}

CRITICAL: Keep ALL 6 roles and ALL bullets from master resume. Only reorder, never drop or add content."""

    message = client.messages.create(
        model="claude-opus-5",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    response_text = ""
    for block in message.content:
        if hasattr(block, "text"):
            response_text += block.text

    try:
        json_str = response_text
        if "```json" in response_text:
            json_str = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            json_str = response_text.split("```")[1].split("```")[0].strip()

        spec = json.loads(json_str)
        return spec
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse spec JSON: {e}\n\n{response_text}")


def build_resume_docx(spec: dict, output_path: str) -> str:
    """Run build_resume.js to generate DOCX from spec.json.

    Returns:
        Path to generated DOCX file
    """
    if not BUILD_SCRIPT_PATH.exists():
        raise FileNotFoundError(f"Build script not found: {BUILD_SCRIPT_PATH}")

    # Write temp spec file
    spec_file = Path(output_path).parent / ".spec.json"
    with open(spec_file, "w") as f:
        json.dump(spec, f, indent=2)

    try:
        # Run build_resume.js
        result = subprocess.run(
            ["node", str(BUILD_SCRIPT_PATH), str(spec_file), output_path],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            raise RuntimeError(f"build_resume.js failed: {result.stderr}")

        if not Path(output_path).exists():
            raise RuntimeError(f"DOCX not generated at {output_path}")

        return output_path

    finally:
        if spec_file.exists():
            spec_file.unlink()


def convert_docx_to_pdf(docx_path: str) -> str:
    """Convert DOCX to PDF using LibreOffice.

    Returns:
        Path to generated PDF file
    """
    pdf_path = str(Path(docx_path).with_suffix(".pdf"))

    try:
        subprocess.run(
            [
                "soffice",
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(Path(docx_path).parent),
                docx_path,
            ],
            capture_output=True,
            timeout=60,
        )

        if not Path(pdf_path).exists():
            raise RuntimeError(f"PDF not generated at {pdf_path}")

        return pdf_path
    except FileNotFoundError:
        raise RuntimeError(
            "LibreOffice not found. Install with: apt install libreoffice-headless"
        )

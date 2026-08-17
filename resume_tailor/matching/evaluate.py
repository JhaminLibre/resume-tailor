import json
from anthropic import Anthropic
from resume_tailor.models import Resume, MatchResult
from resume_tailor.config import DEBUG


def evaluate_job_match(master_resume: Resume, job_title: str, job_description: str) -> MatchResult:
    """Use Claude to evaluate how well a job matches the candidate's resume.

    Compares the job requirements against the candidate's experience, skills, and education.

    Args:
        master_resume: The candidate's master Resume object
        job_title: The job title
        job_description: The full job description text

    Returns:
        MatchResult with score (0-100) and reasoning (strengths, gaps, summary)
    """
    client = Anthropic()

    resume_summary = format_resume_for_evaluation(master_resume)

    prompt = f"""You are an expert recruiter evaluating how well a candidate matches a job opportunity.

CANDIDATE RESUME:
{resume_summary}

JOB TITLE: {job_title}

JOB DESCRIPTION:
{job_description}

Evaluate the candidate's fit for this job. Consider:
1. Required vs. desired skills (how many does the candidate have?)
2. Years of relevant experience
3. Education and certifications
4. Domain knowledge alignment
5. Soft skills and culture fit (to the extent you can infer)

Provide a structured JSON response with:
- match_score: Integer from 0-100 (0=no match, 50=moderate fit, 100=perfect fit)
- summary: 2-3 sentence explanation of the overall fit
- strengths: List of 3-5 key strengths that make this candidate a good fit
- gaps: List of 2-5 areas where the candidate lacks required qualifications (or empty if excellent fit)

Return ONLY valid JSON matching this structure, no explanation before or after."""

    if DEBUG:
        print(f"[DEBUG] Evaluating match for {job_title}")

    message = client.messages.create(
        model="claude-opus-5",
        max_tokens=2048,
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
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

        result_dict = json.loads(json_str)
        match_result = MatchResult(**result_dict)

        if DEBUG:
            print(f"[DEBUG] Match score for {job_title}: {match_result.match_score}")

        return match_result

    except (json.JSONDecodeError, ValueError) as e:
        raise ValueError(
            f"Failed to parse Claude's response as MatchResult JSON: {e}\n\nRaw response:\n{response_text}"
        )


def format_resume_for_evaluation(resume: Resume) -> str:
    """Format a Resume object into human-readable text for evaluation context.

    Args:
        resume: Resume object

    Returns:
        Formatted resume text
    """
    lines = []

    lines.append(f"{resume.contact.full_name}")
    if resume.contact.email:
        lines.append(f"Email: {resume.contact.email}")
    if resume.contact.phone:
        lines.append(f"Phone: {resume.contact.phone}")
    if resume.contact.location:
        lines.append(f"Location: {resume.contact.location}")
    if resume.contact.linkedin_url:
        lines.append(f"LinkedIn: {resume.contact.linkedin_url}")
    lines.append("")

    if resume.summary:
        lines.append("PROFESSIONAL SUMMARY")
        lines.append(resume.summary)
        lines.append("")

    if resume.experience:
        lines.append("EXPERIENCE")
        for exp in resume.experience:
            date_range = f"{exp.start_date}"
            if exp.end_date:
                date_range += f" - {exp.end_date}"
            else:
                date_range += " - Present"

            lines.append(f"{exp.title} at {exp.company} ({date_range})")
            if exp.location:
                lines.append(f"  Location: {exp.location}")
            for bullet in exp.bullets:
                lines.append(f"  • {bullet}")
            lines.append("")

    if resume.education:
        lines.append("EDUCATION")
        for edu in resume.education:
            degree_str = f"{edu.degree}"
            if edu.field_of_study:
                degree_str += f" in {edu.field_of_study}"
            lines.append(f"{degree_str} from {edu.institution}")
            if edu.start_date or edu.end_date:
                date_range = ""
                if edu.start_date:
                    date_range = edu.start_date
                if edu.end_date:
                    date_range += f" - {edu.end_date}"
                if date_range:
                    lines.append(f"  {date_range}")
            lines.append("")

    if resume.skills:
        lines.append("SKILLS")
        for category in resume.skills:
            skills_str = ", ".join(category.items)
            lines.append(f"{category.name}: {skills_str}")
        lines.append("")

    if resume.certifications:
        lines.append("CERTIFICATIONS")
        for cert in resume.certifications:
            cert_str = cert.name
            if cert.issuer:
                cert_str += f" ({cert.issuer})"
            if cert.date:
                cert_str += f" - {cert.date}"
            lines.append(f"  • {cert_str}")
        lines.append("")

    return "\n".join(lines)

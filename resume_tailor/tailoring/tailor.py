import json
from anthropic import Anthropic
from resume_tailor.models import Resume
from resume_tailor.config import DEBUG


def tailor_resume_to_job(
    master_resume: Resume, job_title: str, job_description: str
) -> Resume:
    """Use Claude to tailor a resume to a specific job posting.

    Reorders and emphasizes content to match the job requirements while keeping
    the same Resume schema structure.

    Args:
        master_resume: The candidate's master Resume object
        job_title: The job title
        job_description: The full job description text

    Returns:
        A new Resume object with tailored content (same schema, customized bullets/summary)
    """
    client = Anthropic()

    schema = Resume.model_json_schema()
    master_json = master_resume.model_dump()

    prompt = f"""You are an expert resume writer specializing in tailoring resumes for specific job opportunities.

MASTER RESUME (base content):
{json.dumps(master_json, indent=2)}

JOB OPPORTUNITY:
Title: {job_title}
Description:
{job_description}

Your task: Tailor the master resume to this specific job while maintaining the same JSON structure.

CRITICAL CONSTRAINTS - Do NOT violate these:
1. ONLY change the professional summary to highlight relevant experience
2. ONLY reorder existing bullets/skills/experience - do NOT add new ones
3. ONLY reorder which skills appear first - do NOT add new skills
4. Do NOT add any new roles, projects, education, or sections
5. Do NOT modify dates, company names, institution names, or any factual information
6. Do NOT remove any sections or bullets
7. Keep the exact same number of bullets in each role
8. Keep the exact same number of skills and items in each section
9. The file must fit on 1 page - do not add content that increases length

Your ONLY actions:
- Rewrite the summary to emphasize relevant experience for this job
- Reorder bullets within each experience entry (no new bullets)
- Reorder skills to prioritize relevant ones first (no new skills)
- Reorder education/certifications if relevant

Return a tailored Resume JSON object that:
- Has the exact same schema as the input
- Emphasizes the candidate's best fit for this specific job
- Still accurately represents the candidate (no fabrication)
- Only reorders/reemphasizes content from the master resume

Return ONLY valid JSON matching the Resume schema, no explanation before or after."""

    if DEBUG:
        print(f"[DEBUG] Tailoring resume for {job_title}")

    message = client.messages.create(
        model="claude-opus-5",
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
    )

    response_text = message.content[0].text

    try:
        json_str = response_text
        if "```json" in response_text:
            json_str = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            json_str = response_text.split("```")[1].split("```")[0].strip()

        tailored_dict = json.loads(json_str)
        tailored_resume = Resume(**tailored_dict)

        if DEBUG:
            print(f"[DEBUG] Successfully tailored resume for {job_title}")

        return tailored_resume

    except (json.JSONDecodeError, ValueError) as e:
        raise ValueError(
            f"Failed to parse Claude's response as tailored Resume JSON: {e}\n\nRaw response:\n{response_text}"
        )

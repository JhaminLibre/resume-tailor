import json
from anthropic import Anthropic
from resume_tailor.models import Resume


def structure_resume_with_claude(raw_text: str) -> Resume:
    """Use Claude to structure raw resume text into a Resume object.

    Args:
        raw_text: Extracted resume text

    Returns:
        Structured Resume object
    """
    client = Anthropic()

    schema = Resume.model_json_schema()

    prompt = f"""You are a resume parsing expert. Extract and structure the following resume text into a well-organized JSON object.

IMPORTANT GUIDELINES:
- Extract all contact information (name, email, phone, location, LinkedIn, GitHub, portfolio URLs)
- Summarize the candidate's professional summary or objective in 2-3 sentences
- List all work experience entries with company, title, location, dates (YYYY-MM format), and key bullet points
- List education with institution, degree, field of study, and dates
- Group skills into categories (e.g., "Languages", "Cloud/Infrastructure", "Databases", "Tools")
- Extract certifications and projects if present
- For dates, use YYYY-MM format (e.g., "2023-01" for January 2023). Use "2024-present" or similar for ongoing roles.
- If a field is missing or unclear, use null or an empty list as appropriate
- Ensure all bullet points are concise and action-oriented

Here is the raw resume text:

---
{raw_text}
---

Extract and return ONLY a valid JSON object matching this schema:
{json.dumps(schema, indent=2)}"""

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

        resume_dict = json.loads(json_str)
        resume = Resume(**resume_dict)
        return resume
    except (json.JSONDecodeError, ValueError) as e:
        raise ValueError(
            f"Failed to parse Claude's response as Resume JSON: {e}\n\nRaw response:\n{response_text}"
        )

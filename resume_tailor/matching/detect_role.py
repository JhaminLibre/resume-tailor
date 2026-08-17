def detect_job_role(job_title: str, job_description: str = "") -> str:
    """Detect job role type from title and description.

    Args:
        job_title: Job title
        job_description: Full job description (optional)

    Returns:
        Role tag: 'strategy-analytics', 'pm', or 'analytics-engineer'
    """
    text = f"{job_title} {job_description}".lower()

    # Check for analytics-engineer
    if any(
        word in text
        for word in [
            "analytics engineer",
            "analytics-engineer",
            "data engineer",
            "data-engineer",
            "data analyst",
        ]
    ):
        return "analytics-engineer"

    # Check for product manager
    if any(
        word in text
        for word in ["product manager", "pm ", "product lead", "associate pm"]
    ):
        return "pm"

    # Check for strategy/business
    if any(
        word in text
        for word in ["strategy", "business analyst", "analytics manager", "senior analyst"]
    ):
        return "strategy-analytics"

    # If unsure, make a best guess based on what's present
    if "engineer" in text or "data" in text:
        return "analytics-engineer"
    elif "product" in text or "manager" in text:
        return "pm"
    else:
        return "strategy-analytics"

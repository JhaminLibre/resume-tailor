import re
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs


class JobCandidate:
    """Represents a job extracted from a LinkedIn alert email."""

    def __init__(
        self,
        title: str,
        company: str,
        linkedin_url: str,
        snippet: str = "",
        location: str = "",
    ):
        self.title = title
        self.company = company
        self.linkedin_url = normalize_linkedin_url(linkedin_url)
        self.snippet = snippet.strip()
        self.location = location.strip()

    def __repr__(self):
        return f"JobCandidate(title={self.title}, company={self.company}, url={self.linkedin_url})"


def normalize_linkedin_url(url: str) -> str:
    """Normalize a LinkedIn job URL by stripping tracking parameters.

    LinkedIn alert emails often include per-email tracking params; this strips them
    so the same job posting doesn't create duplicate rows if it appears in multiple emails.

    Args:
        url: LinkedIn job URL (possibly with query params)

    Returns:
        Normalized URL with tracking params removed
    """
    if not url.startswith("http"):
        url = "https://" + url

    parsed = urlparse(url)
    path_parts = parsed.path.split("/")

    job_id = None
    for i, part in enumerate(path_parts):
        if part == "jobs" and i + 1 < len(path_parts):
            job_id = path_parts[i + 1]
            break

    if job_id:
        return f"https://www.linkedin.com/jobs/view/{job_id}/"

    return url


def parse_linkedin_alert_html(html: str) -> list[JobCandidate]:
    """Parse LinkedIn job-alert email HTML to extract job candidates.

    LinkedIn alert emails typically contain a list of recommended jobs with title,
    company, snippet, and a link to the full posting.

    Args:
        html: Email body HTML from LinkedIn alert

    Returns:
        List of JobCandidate objects extracted from the email
    """
    soup = BeautifulSoup(html, "lxml")
    jobs = []

    job_elements = soup.find_all("td", {"data-test-id": re.compile("job-card-container")})

    if not job_elements:
        job_elements = soup.find_all(class_=re.compile("job-card|job-item", re.IGNORECASE))

    if not job_elements:
        job_elements = soup.find_all(href=re.compile(r"linkedin\.com/jobs/view"))

    for elem in job_elements[:5]:
        title = ""
        company = ""
        url = ""
        snippet = ""
        location = ""

        title_elem = elem.find(class_=re.compile("job-title|title", re.IGNORECASE))
        if not title_elem:
            title_elem = elem.find("a", href=re.compile(r"linkedin\.com/jobs"))
        if title_elem:
            title = title_elem.get_text(strip=True)

        company_elem = elem.find(class_=re.compile("company|company-name", re.IGNORECASE))
        if not company_elem:
            company_elem = elem.find(string=re.compile(r"@|Company"))
        if company_elem:
            company = company_elem.get_text(strip=True)

        url_elem = elem.find("a", href=re.compile(r"linkedin\.com/jobs/view/\d+"))
        if url_elem and url_elem.get("href"):
            url = url_elem["href"]

        snippet_elem = elem.find(class_=re.compile("snippet|description", re.IGNORECASE))
        if snippet_elem:
            snippet = snippet_elem.get_text(strip=True)

        location_elem = elem.find(class_=re.compile("location", re.IGNORECASE))
        if location_elem:
            location = location_elem.get_text(strip=True)

        if title and url:
            job = JobCandidate(
                title=title,
                company=company or "Unknown Company",
                linkedin_url=url,
                snippet=snippet,
                location=location,
            )
            jobs.append(job)

    return jobs

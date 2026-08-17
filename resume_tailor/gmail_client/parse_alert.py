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
    print(f"[DEBUG] parse_linkedin_alert_html called with {len(html)} bytes of HTML")
    soup = BeautifulSoup(html, "lxml")
    jobs = []

    job_cards = soup.find_all("td", {"data-test-id": "job-card"})
    print(f"[DEBUG] Found {len(job_cards)} job cards with data-test-id='job-card'")

    if not job_cards:
        all_tds = soup.find_all("td")
        print(f"[DEBUG] Total TD elements: {len(all_tds)}")
        for td in all_tds[:3]:
            print(f"[DEBUG] Sample TD attrs: {td.attrs}")

    for i, card in enumerate(job_cards[:5]):
        title = ""
        company = ""
        url = ""
        location = ""

        job_link = card.find("a", href=re.compile(r"linkedin\.com/comm/jobs/view/\d+"))
        print(f"[DEBUG] Card {i}: Found job_link? {job_link is not None}")

        if job_link:
            url = job_link.get("href", "")
            print(f"[DEBUG] Card {i}: url={url[:50] if url else 'EMPTY'}...")
            if not url:
                continue

            all_links_in_card = card.find_all("a")
            if len(all_links_in_card) > 2:
                title = all_links_in_card[2].get_text(strip=True)

            paragraphs = card.find_all("p", class_="text-system-gray-100")
            print(f"[DEBUG] Card {i}: Found {len(paragraphs)} paragraphs")
            if paragraphs:
                location_text = paragraphs[0].get_text(strip=True)
                if "·" in location_text:
                    parts = location_text.split("·")
                    company = parts[0].strip()
                    location = "·".join(parts[1:]).strip()
                else:
                    company = location_text


        print(f"[DEBUG] Card {i}: Checking - title={bool(title)}, url={bool(url)}")
        if title and url:
            job = JobCandidate(
                title=title,
                company=company or "Unknown Company",
                linkedin_url=url,
                location=location,
            )
            jobs.append(job)
            print(f"[DEBUG] Card {i}: ✓ Added job: {title}")

    print(f"[DEBUG] Extracted {len(jobs)} jobs total")
    return jobs

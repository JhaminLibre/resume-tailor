# resume-tailor

Automatically tailor your resume to job postings from LinkedIn job-alert emails. Uses Claude API to evaluate job fit, generate tailored resumes, and render polished PDFs — all from your Gmail inbox.

## Features

- **Automated job monitoring** — Fetches LinkedIn job-alert emails from Gmail hourly
- **Smart matching** — Claude API evaluates each job against your master resume (0-100 score)
- **Intelligent fallbacks** — Tries LinkedIn job page → company careers site → email snippet
- **Resume tailoring** — Claude reorders and emphasizes your experience for each job
- **PDF generation** — ATS-friendly resume PDFs ready to apply with
- **Application tracking** — SQLite DB tracks companies, jobs, resumes, and application status
- **Fully automated** — systemd timer runs hourly checks without manual intervention

## Quick Start

### 1. Prerequisites

- Python 3.10+
- Gmail account with job-alert emails from LinkedIn
- Anthropic API key (Claude access)
- Google Cloud project with Gmail API enabled

### 2. Install Dependencies

```bash
cd ~/dev/resume-tailor
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Verify WeasyPrint system dependencies:
```bash
sudo apt install libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf2.0-0
```

### 3. Set Up Environment

Copy `.env.example` to `.env` and add your API key:
```bash
cp .env.example .env
# Edit .env with your ANTHROPIC_API_KEY
```

### 4. Set Up Gmail API Access

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a new project: "resume-tailor"
3. Enable the **Gmail API** (APIs & Services → Library)
4. Set up **OAuth consent screen**:
   - User type: External
   - App name: Resume Tailor
   - Scopes: `https://www.googleapis.com/auth/gmail.readonly`
   - Test users: Add your Gmail address
5. Create **OAuth 2.0 credential** (Desktop app)
6. Download the JSON and save to `data/gmail_credentials.json`

### 5. Import Your Resume

```bash
resume-tailor import-resume ~/path/to/your/resume.pdf
# or
resume-tailor import-resume ~/path/to/your/resume.docx
```

Follow the prompts to review and confirm the structured resume JSON.

### 6. Run Your First Check

```bash
resume-tailor check
```

This will:
- Fetch new LinkedIn job-alert emails
- Extract and deduplicate job postings
- Evaluate each job against your master resume
- Tailor resumes for jobs scoring ≥70 (configurable)
- Render PDFs to `output/` directory
- Track applications in the database

### 7. (Optional) Set Up Hourly Automation

Copy systemd files to your user config:

```bash
mkdir -p ~/.config/systemd/user
cp scripts/resume-tailor.service ~/.config/systemd/user/
cp scripts/resume-tailor.timer ~/.config/systemd/user/

# Edit the service file to match your paths:
sed -i "s|/home/mpennisi|$HOME|g" ~/.config/systemd/user/resume-tailor.service

# Enable and start the timer
systemctl --user daemon-reload
systemctl --user enable resume-tailor.timer
systemctl --user start resume-tailor.timer

# Check status
systemctl --user status resume-tailor.timer
journalctl --user -u resume-tailor.service -f
```

## Commands

```bash
# Import a resume from PDF or DOCX
resume-tailor import-resume <file>

# Check for new job alerts and process them
resume-tailor check [--threshold SCORE]

# List stored resumes
resume-tailor list-resumes
```

## Configuration

Set in `.env`:

```bash
ANTHROPIC_API_KEY=sk-...          # Required: Claude API key
MATCH_THRESHOLD=70                 # Default: 70 (0-100 match score)
DEBUG=false                        # Set to true for verbose logging
```

## How It Works

### Pipeline (per `resume-tailor check` run)

1. **Fetch emails** — Query Gmail for new LinkedIn job-alert emails
2. **Parse jobs** — Extract job title, company, URL, snippet from email HTML
3. **Deduplicate** — Skip already-seen emails and jobs (by normalized URL)
4. **Fetch full JD** — Try LinkedIn fetch → company site search → fallback to snippet
5. **Evaluate match** — Claude scores job vs. your master resume (considers skills, experience, requirements)
6. **Tailor resume** — For jobs ≥ threshold, Claude reorders/emphasizes your experience
7. **Render PDF** — Generate a polished, ATS-friendly resume PDF
8. **Track application** — Create/update application record in database

### Database Schema

- **companies** — Company name, industry, location
- **jobs** — Job title, company, URL, description (with source tracking)
- **evaluations** — Match score, reasoning, model used
- **resumes** — Master resume + tailored variants per job (as JSON + PDF path)
- **applications** — Job ↔ resume mapping, application status tracking
- **emails_processed** — Dedup by Gmail message ID

## Troubleshooting

### Gmail OAuth: "Sign in to your Google Account"

First run opens a browser for consent. If no browser is available (WSL2), manually copy the URL into a Windows browser and paste the auth code back into the terminal.

### "No master resume found"

Run `resume-tailor import-resume <file>` first. The master resume is required for all matching.

### "LinkedIn job description could not be fetched"

The job page may require login or be blocked. The tool falls back to the company careers site, then the email snippet. Use `resume-tailor set-jd <job_id>` to manually provide the full description.

### Systemd timer not firing

Check logs:
```bash
journalctl --user -u resume-tailor.service
systemctl --user status resume-tailor.timer
```

Ensure the timer is enabled:
```bash
systemctl --user enable resume-tailor.timer
systemctl --user start resume-tailor.timer
```

## Architecture

```
resume_tailor/
├── importer/        # PDF/DOCX extraction + Claude structuring
├── gmail_client/    # Gmail OAuth + email fetching + parsing
├── jd/              # Tiered job description fetching
├── matching/        # Claude-powered job evaluation
├── tailoring/       # Claude-powered resume tailoring
├── rendering/       # Jinja2 + WeasyPrint PDF generation
├── cli.py           # Click CLI commands
├── db.py            # SQLite schema + CRUD
├── pipeline.py      # Email → jobs orchestration
└── config.py        # Settings + paths
```

## FAQ

**Q: Does this scrape LinkedIn?**
No. It parses emails from LinkedIn's own job-alert digest, which is publicly available in your Gmail inbox.

**Q: Will this get my LinkedIn account flagged?**
No account credentials are needed. The tool only reads emails from Gmail and fetches publicly available job pages via standard HTTP requests.

**Q: How often does it check for new jobs?**
By default, hourly via systemd timer (configurable). You can also run `resume-tailor check` manually anytime.

**Q: Does it automatically apply for me?**
No. It generates tailored resumes and tracks application status manually. You still apply yourself on LinkedIn/company sites.

**Q: Can I edit the tailored resume before applying?**
Yes. Tailored resumes are saved as JSON + PDF. You can edit the PDF or JSON and re-render.

## Limitations & Future Work

- LinkedIn job URLs sometimes require login to view full descriptions; falls back gracefully to snippet or company site
- ~5 jobs per alert email (LinkedIn's email digest limit)
- Application status must be updated manually (user knows when they've actually applied)
- v1 uses a clean ATS-friendly template; custom templates/styling can be added later

## License

MIT

## Support

Issues and feedback: [GitHub Issues](https://github.com/JhaminLibre/resume-tailor/issues)

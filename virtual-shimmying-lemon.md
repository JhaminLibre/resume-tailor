# resume-tailor: Implementation Plan

## Context

You want to stop manually tracking LinkedIn job alerts and hand-tailoring resumes for each one. The goal: automatically pull job postings from your LinkedIn job-alert emails (via Gmail), score how well each matches your actual experience, and generate a tailored, ready-to-submit PDF resume only for the good matches — plus track which jobs you've actually applied to and their status over time (companies, jobs, resumes, applications as related records, not a flat list).

The repo (`~/dev/resume-tailor`, private, pushed to `github.com/JhaminLibre/resume-tailor`) is currently empty except `.gitignore` and an unused `.venv` (Python 3.10.12) — this is a from-scratch build.

**Key decisions already made with you:**
- Job source: parse LinkedIn job-alert **emails via Gmail** (not scraping LinkedIn directly — avoids ToS/ban risk)
- Matching: Claude API scores each job against your resume; only jobs above a threshold get tailored
- Output: polished, ready-to-submit **PDF**
- Automation: runs on-demand first, wired to **poll hourly** via systemd timer once proven (true push via Gmail Pub/Sub rejected — needs a public webhook endpoint + 7-day watch renewal, not worth it for job-alert latency)
- Data model: **relational** — companies, jobs, resumes (master + tailored), applications — not a flat table, with `application_status` manually updatable since only you know when you've actually applied/heard back

---

## 1. Master resume — Pydantic schema

Your PDF/DOCX resumes get parsed **once** into a structured JSON "master resume" — the source of truth for every future tailoring pass.

```python
class ContactInfo(BaseModel):
    full_name: str
    email: str
    phone: str | None = None
    location: str | None = None
    linkedin_url: str | None = None
    github_url: str | None = None
    portfolio_url: str | None = None

class ExperienceEntry(BaseModel):
    company: str
    title: str
    location: str | None = None
    start_date: str              # "YYYY-MM"
    end_date: str | None = None  # None = present
    bullets: list[str]
    tags: list[str] = []         # keywords for matching/tailoring emphasis

class EducationEntry(BaseModel):
    institution: str
    degree: str
    field_of_study: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    gpa: str | None = None
    honors: list[str] = []

class SkillCategory(BaseModel):
    name: str            # "Languages", "Cloud/Infra", ...
    items: list[str]

class Certification(BaseModel):
    name: str
    issuer: str | None = None
    date: str | None = None

class Project(BaseModel):
    name: str
    description: str | None = None
    bullets: list[str] = []
    url: str | None = None

class Resume(BaseModel):
    contact: ContactInfo
    summary: str
    experience: list[ExperienceEntry]
    education: list[EducationEntry]
    skills: list[SkillCategory]
    certifications: list[Certification] = []
    projects: list[Project] = []
```

A **tailored resume** is the same `Resume` shape, generated per job — the master is never mutated by tailoring. Pydantic gives runtime validation on load/save and `.model_json_schema()` to drive Claude's structured-output calls for import, evaluation, and tailoring — one schema, three uses.

---

## 2. Relational data store — SQLite

SQLite via stdlib `sqlite3` (not JSON-lines/flat file): you need repeated in-place status updates per job, filtering/joins for `list`, and atomic dedup — SQLite gives all three with zero extra dependencies.

```sql
PRAGMA foreign_keys = ON;

CREATE TABLE emails_processed (
    gmail_message_id   TEXT PRIMARY KEY,
    received_at        TEXT NOT NULL,
    processed_at       TEXT NOT NULL DEFAULT (datetime('now')),
    jobs_extracted     INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE companies (
    company_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    company_name    TEXT NOT NULL UNIQUE,
    industry        TEXT,
    location        TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE jobs (
    job_id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    job_title                 TEXT NOT NULL,
    company_id                INTEGER NOT NULL REFERENCES companies(company_id),
    location                  TEXT,
    linkedin_url              TEXT NOT NULL UNIQUE,   -- primary dedup key
    snippet                   TEXT,
    full_description          TEXT,
    full_description_source   TEXT NOT NULL DEFAULT 'snippet_only'
                              CHECK (full_description_source IN
                                  ('linkedin_fetch','company_site_fetch','snippet_only','manual_paste')),
    date_found                TEXT NOT NULL,
    date_added                TEXT NOT NULL DEFAULT (datetime('now')),
    status                    TEXT NOT NULL DEFAULT 'new'
                              CHECK (status IN ('new','evaluated','tailored','skipped','error')),
    created_at                TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at                TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_jobs_company ON jobs(company_id);
CREATE INDEX idx_jobs_status  ON jobs(status);

CREATE TABLE evaluations (
    evaluation_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id            INTEGER NOT NULL REFERENCES jobs(job_id),
    match_score       INTEGER NOT NULL CHECK (match_score BETWEEN 0 AND 100),
    match_reasoning   TEXT NOT NULL,   -- JSON: {"summary","strengths":[...],"gaps":[...]}
    model_used        TEXT,
    evaluated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_evaluations_job ON evaluations(job_id);

CREATE TABLE resumes (
    resume_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    resume_name   TEXT NOT NULL,        -- "master" or "Acme Corp - Senior Engineer"
    resume_type   TEXT NOT NULL CHECK (resume_type IN ('master','tailored')),
    job_id        INTEGER REFERENCES jobs(job_id),  -- NULL for master; set for tailored
    content_json  TEXT NOT NULL,        -- the structured Resume JSON
    file          TEXT,                 -- path to rendered PDF
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK ( (resume_type='master' AND job_id IS NULL)
         OR (resume_type='tailored' AND job_id IS NOT NULL) )
);
CREATE INDEX idx_resumes_job ON resumes(job_id);

CREATE TABLE applications (
    application_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id              INTEGER NOT NULL UNIQUE REFERENCES jobs(job_id),
    resume_id           INTEGER REFERENCES resumes(resume_id),
    applied_at          TEXT,           -- NULL until you actually apply
    application_status  TEXT NOT NULL DEFAULT 'not_applied'
                         CHECK (application_status IN
                             ('not_applied','applied','interviewing','rejected','offer','accepted')),
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
);
```

**Why `evaluations` is its own table:** a score is a judgment tied to a snapshot of your master resume at a point in time, not an intrinsic job property — keeping it separate lets a job be re-scored later (e.g. after you edit your master resume) without a migration; take the latest `evaluated_at` per `job_id` as current.

**Lifecycle:** an `applications` row is auto-created (`status='not_applied'`) the moment a tailored resume is generated, so there's always a row to update once you actually apply. `mark-applied` / `update-status` commands (below) are the only way `application_status` changes — the pipeline never guesses whether you applied.

**Dedup:** `jobs.linkedin_url` is unique, but LinkedIn alert links often carry per-email tracking query params for the *same* posting — the ingestion step must normalize the URL (strip tracking params, extract the LinkedIn job's numeric ID from the path) before the uniqueness check, or you'll get duplicate rows for one job.

---

## 3. Dependencies

| Concern | Library | Why |
|---|---|---|
| CLI | `click` | Mature, simple subcommands, testable |
| PDF text extraction | `pdfplumber` (fallback `pypdf`) | Preserves reading order better for multi-column resumes |
| DOCX extraction | `python-docx` | Standard, structure-aware |
| Gmail API | `google-api-python-client`, `google-auth-oauthlib`, `google-auth-httplib2` | Google's own OAuth installed-app stack |
| Email HTML parsing | `beautifulsoup4` + `lxml` | Parse LinkedIn alert HTML into job candidates |
| Full JD fetch | `requests` + `trafilatura` | `trafilatura` strips boilerplate from arbitrary job-page HTML, more robust than hand-rolled selectors |
| Company-site fallback search | `ddgs` (duckduckgo-search) | Free, no API key, used only to locate a company's own careers-page/ATS listing for a job when the LinkedIn fetch is truncated — not used against LinkedIn itself |
| Claude API | `anthropic` (official SDK) | Structured-output calls driven by the shared `Resume`/`MatchResult` Pydantic schemas |
| Schema/validation | `pydantic` v2 | Backs `Resume`, `MatchResult`; generates JSON schema for Claude |
| PDF generation | `WeasyPrint` + `Jinja2` | HTML/CSS → PDF, full typographic control, no headless browser. **Needs system libs** (Pango/cairo/gdk-pixbuf) — verify `apt install` works in Phase 0 |
| Config | `python-dotenv` | Load `ANTHROPIC_API_KEY` etc. from a gitignored `.env` |
| CLI tables | `rich` | Nice `list` output (optional polish) |
| Testing | `pytest` | Standard |

Managed via `pyproject.toml` with `[project.scripts] resume-tailor = "resume_tailor.cli:main"`, installed with `pip install -e .` into the existing `.venv`.

---

## 4. Module structure

```
resume-tailor/
├── .gitignore                     # extend: data/, output/, .env, *token.json
├── pyproject.toml
├── .env.example
├── README.md
├── data/                          # gitignored — local state
│   ├── state.db
│   ├── gmail_credentials.json     # OAuth client secret
│   └── gmail_token.json           # cached OAuth token
├── output/                        # gitignored — generated PDFs
│   └── <company>-<role>-<YYYY-MM-DD>.pdf
├── resume_tailor/
│   ├── cli.py                     # click group + subcommands
│   ├── config.py                  # env/paths/default threshold
│   ├── models.py                  # Resume, MatchResult, etc.
│   ├── db.py                      # sqlite init + CRUD
│   ├── importer/
│   │   ├── extract_text.py        # PDF/DOCX -> raw text
│   │   └── structure_resume.py    # raw text -> Resume via Claude
│   ├── gmail_client/
│   │   ├── auth.py                # OAuth flow + token refresh
│   │   ├── fetch.py                # search/fetch alert emails
│   │   └── parse_alert.py          # alert HTML -> job candidates
│   ├── jd/
│   │   ├── fetch_jd.py             # tiered JD resolution: LinkedIn -> company site -> snippet
│   │   ├── fetch_linkedin.py       # requests + trafilatura against the LinkedIn URL
│   │   └── fetch_company_site.py   # ddgs search -> identify company/ATS domain -> trafilatura fetch
│   ├── matching/
│   │   └── evaluate.py             # Claude call -> MatchResult
│   ├── tailoring/
│   │   └── tailor.py               # Claude call -> tailored Resume
│   ├── rendering/
│   │   ├── templates/resume.html.j2
│   │   ├── templates/resume.css
│   │   └── render_pdf.py           # Jinja2 + WeasyPrint -> PDF
│   └── pipeline.py                 # orchestrates `check` end-to-end
└── tests/
```

---

## 5. Build order (smallest useful slice first)

1. **Phase 0 — Scaffolding.** `pyproject.toml`, install deps into existing `.venv`, directory tree, extend `.gitignore`, verify WeasyPrint's system libs install cleanly on this WSL2 box (don't discover this late).
2. **Phase 1 — Master resume import.** `extract_text.py` → `structure_resume.py` (Claude structured output) → `resume-tailor import-resume <file>` writes a `resumes` row (`resume_type='master'`). Explicit review step before anything downstream uses it. **Deliverable: a real, reviewed master resume in the DB.**
3. **Phase 2 — DB layer + `list`.** `db.py` CRUD, `resume-tailor list` (joins jobs→companies→evaluations→applications). Testable with dummy rows before Gmail/Claude exist.
4. **Phase 3 — Gmail read access.** Google Cloud OAuth setup (below) → `auth.py` → `fetch.py` → `parse_alert.py`. Temporary `debug-fetch-emails` command prints parsed candidates without touching the DB — verify parsing against your real inbox first.
5. **Phase 4 — Dedup + persistence.** Wire Phase 3 into `companies`/`jobs` tables with URL normalization; skip already-processed `gmail_message_id`s.
6. **Phase 5 — Full JD fetch, tiered fallback.** `fetch_jd.py` resolves each job's description in order: (a) `fetch_linkedin.py` — `requests`+`trafilatura` against the LinkedIn URL, detecting truncation/login-wall markers → `full_description_source='linkedin_fetch'` on success; (b) `fetch_company_site.py` — if (a) fails, search `"<company> careers <job title>"` via `ddgs`, prefer the company's own domain or a known ATS (Greenhouse/Lever/Workday/Ashby/SmartRecruiters/iCIMS/Jobvite), fetch via `trafilatura` → `full_description_source='company_site_fetch'` on success; (c) if both fail, fall back to the email snippet (`full_description_source='snippet_only'`), evaluation proceeds with a "limited information" caveat. `resume-tailor set-jd <job_id>` remains available anytime for manual paste (`full_description_source='manual_paste'`).
7. **Phase 6 — Matching.** `evaluate.py` scores every job with an available JD; `list`/`show <job_id>` surface scores and reasoning.
8. **Phase 7 — Tailoring + PDF rendering.** Tailor only jobs ≥ threshold (default ~70–75, configurable via `--threshold`/env); render to `output/<company>-<role>-<date>.pdf`; auto-create the matching `applications` row (`status='not_applied'`). Add `resume-tailor mark-applied <job_id>` and `update-status <job_id> <status>`. Assemble `pipeline.py` for the full `check` command with a run summary.
9. **Phase 8 — Hardening.** Per-job error isolation (one bad job → `status='error'`, doesn't kill the run), logging, `pytest` coverage for deterministic modules, README.
10. **Phase 9 — Automation.** Confirm the Gmail token refreshes unattended. Wire a **systemd user timer** (preferred over cron on WSL2 — `Persistent=true` catches up after a missed/offline window instead of silently skipping) running `resume-tailor check` **hourly**, not daily. Rejected true push (Gmail Pub/Sub webhook): would need a publicly reachable HTTPS endpoint plus a recurring `watch()` renewal every 7 days — meaningfully more infrastructure for a latency gain that doesn't matter for job-alert timing. Hourly polling is simpler and plenty timely in practice.

---

## 6. Gmail API setup

1. console.cloud.google.com → new project ("resume-tailor") → enable **Gmail API**.
2. OAuth consent screen: External user type, scope `gmail.readonly` only, add `matt.pennisi@gmail.com` as a test user (stays in Testing status — avoids full app verification).
3. Credentials → OAuth client ID → **Desktop app** → download JSON as `data/gmail_credentials.json` (gitignored).
4. First run: `InstalledAppFlow.run_local_server(port=0)` opens a browser for consent, caches token (incl. refresh token) to `data/gmail_token.json`. **WSL2 note:** test whether a browser is reachable from WSL directly; if not, use the console-based copy/paste flow as fallback.
5. Later runs auto-refresh from the cached token; only re-prompts if the refresh token itself becomes invalid — worth watching for under Testing-status app policies (flagged risk below).

---

## 7. Flagged decisions (sensible defaults chosen, can be tuned later)

- **Full-JD fetch fallback:** three-tier resolution (LinkedIn fetch → company-site search fetch → snippet-only), each stage graceful rather than blocking — `set-jd` lets you backfill manually anytime. Confirmed with you.
- **Jobs-per-alert-email limit (~5):** LinkedIn's alert email itself only lists a handful of jobs; this is a constraint of the email digest format, not something the pipeline can widen without deeper LinkedIn access (e.g. logging in as you, which you've flagged as too risky). Accepted as-is — not in scope to "fix."
- **Match threshold:** default ~70–75, override via `--threshold`/env — tune after seeing real scores.
- **Master resume review depth:** Phase 1 pauses for review before anything consumes the JSON, but how thorough you make that review is up to you.
- **PDF visual style:** starts with one clean, ATS-friendly template rather than replicating your original resume's exact look (much lower effort/risk) — can revisit later.
- **Gmail token longevity in Testing-status apps:** worth confirming directly during Phase 3/9; worst case is an occasional manual re-auth, not a blocker.

---

## Verification

- Phase 1: run `import-resume` against your real PDF/DOCX, inspect the resulting `Resume` JSON for accuracy against the source file.
- Phase 2: insert dummy rows directly via `db.py`, confirm `list` renders correctly.
- Phase 3: run `debug-fetch-emails` against your actual Gmail inbox, confirm parsed job candidates (title/company/URL) look right.
- Phase 4–6: run `check` repeatedly — confirm no duplicate jobs on second run, confirm scores/reasoning appear in `list`/`show`.
- Phase 7: run `check` end-to-end, open a generated PDF, confirm it renders correctly and content is sensibly tailored; confirm an `applications` row was created.
- Phase 8: run `pytest`.
- Phase 9: confirm the systemd timer fires (`journalctl --user -u resume-tailor`) and a token refresh succeeds unattended.

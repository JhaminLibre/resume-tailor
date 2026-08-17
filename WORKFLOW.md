# Resume Tailor Workflow

Complete end-to-end workflow for automated job finding + skill-based resume tailoring.

## Setup

1. **Install dependencies**
   ```bash
   cd ~/dev/resume-tailor
   pip install -e .
   apt install libreoffice-headless nodejs  # For PDF conversion and resume building
   ```

2. **Import your master resumes** (3 role types)
   ```bash
   resume-tailor import-resume <path-to-strategy.docx> --role strategy-analytics
   resume-tailor import-resume <path-to-pm.docx> --role pm
   resume-tailor import-resume <path-to-analytics.docx> --role analytics-engineer
   ```

3. **Set up Gmail OAuth** — Follow prompts in first `check` run

## Automated Job Fetching

### Manual run (testing)
```bash
resume-tailor check
```

Fetches jobs from LinkedIn email alerts, saves to database. Shows summary of new jobs found.

### Hourly automation
Setup systemd timer to run hourly:
```bash
systemctl --user enable resume-tailor.timer
systemctl --user start resume-tailor.timer
```

View logs:
```bash
journalctl --user -u resume-tailor
```

## Manual Resume Tailoring (with skill)

When you're ready to tailor resumes:

### Step 1: Trigger the skill
```
Hey, can you help me review and tailor resumes for the jobs I have pending?
```

The skill will:
1. Load NEW/UNAPPLIED jobs from your resume-tailor database
2. Score each against your background using the skill's criteria
3. Present a shortlist by fit tier (Strong fit / Worth a look / Weak fit)

### Step 2: Select jobs to tailor
Tell the skill which jobs you want to apply to. It will:
1. Read your master resume templates
2. Generate tailored summaries + reorder skills/bullets for each job
3. Generate DOCX + PDF resumes with your exact formatting
4. Show you the job links + resume paths

### Step 3: Review & Apply
- Open resumes in Windows Explorer: `resume-tailor open-resume <job_id>`
- Review the tailored resume
- Apply to the job on LinkedIn/company site

### Step 4: Mark as applied
After applying, tell the skill or run:
```bash
resume-tailor mark-applied <job_id>
```

The job is now marked as "applied" in your database and won't clutter future reviews.

## Checking Application Status

### See active applications (not applied yet)
```bash
resume-tailor active-applications
```

Shows all jobs you haven't applied to yet, with scores and tailored resume paths.

### List all applications
```bash
resume-tailor list-applications
```

Shows all tailored resumes (applied + not applied yet).

## Database Structure

Jobs are tracked through these statuses:
- `new` — Just fetched, not yet evaluated
- `evaluated` — Scored by the skill, score stored in DB
- `tailored` — Resume generated for this job
- `not_applied` — Tailored but you haven't submitted yet
- `applied` — You submitted an application
- `interviewing` / `offer` / `rejected` / `accepted` — Update these manually as you progress

## Workflow Summary

```
┌─────────────────────────────────────────┐
│  Hourly: resume-tailor check            │
│  (Fetches jobs from LinkedIn alerts)    │
│  Saves to: ~/dev/resume-tailor/data/state.db
└────────────┬────────────────────────────┘
             │
             ↓
┌─────────────────────────────────────────┐
│  Manual: Trigger job-search-analytics   │
│  (Skill scores & tailors resumes)       │
│  Generates: ~/dev/resume-tailor/output/*.docx & .pdf
└────────────┬────────────────────────────┘
             │
             ↓
┌─────────────────────────────────────────┐
│  You: Review tailored resumes           │
│  resume-tailor open-resume <job_id>     │
└────────────┬────────────────────────────┘
             │
             ↓
┌─────────────────────────────────────────┐
│  You: Apply to jobs on LinkedIn         │
└────────────┬────────────────────────────┘
             │
             ↓
┌─────────────────────────────────────────┐
│  You: Mark as applied                   │
│  resume-tailor mark-applied <job_id>    │
│  Or tell the skill "I applied!"         │
└─────────────────────────────────────────┘
```

## Tips

- The skill's scoring is thorough — it evaluates seniority, skill gaps, domain fit, and whether the role balances hands-on + strategic work
- "Worth a look, flag the gap" means it's a good fit but has one real mismatch worth thinking about before applying
- Your master resumes are the source of truth — the skill never invents content, only reorders and reframes what's already there
- All 6 roles and all bullets are always included in tailored resumes — the formatting is your template, the content is selective
- Resumes are saved with the company name for easy identification

## Troubleshooting

**No jobs showing up?**
- Check Gmail is authenticated: `resume-tailor check` should show emails fetched
- Check jobs are being saved: `resume-tailor list-applications` should show them (once tailored)

**Resumes look wrong?**
- Make sure you imported 3 master resumes (strategy, PM, analytics)
- The skill picks the right one based on job title detection

**Mark-applied not working?**
- Tell the skill directly: "I applied to [company]" and it will update for you
- Or run: `resume-tailor mark-applied <job_id>` with the ID from `active-applications`

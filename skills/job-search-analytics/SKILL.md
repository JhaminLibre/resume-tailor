---
name: job-search-analytics
description: Run Matthew Pennisi's recurring job search — search for open roles across three vectors (analytics engineer, data-focused PM, strategic/data-analytics IC roles like Faire/Broccoli), score each against his real experience, present a shortlist for review, and generate a tailored resume (docx + pdf) for whichever ones he chooses to apply to. Trigger this whenever Matthew asks to search/check for jobs, find new openings, run his job search, or says something like "any new roles out there" — even if he doesn't name all three vectors explicitly. Also trigger for "tailor a resume for X" once a specific job is chosen from a prior run.
---

# Job Search — Matthew Pennisi

This skill runs a recurring workflow: search → score → review → tailor. Matthew
is a strategy/analytics leader with 10+ years, evaluating roles the way a
thoughtful recruiter would — honest about both strong fits and real mismatches,
never inflating his background to make a role look better than it is.

Read `assets/resume_master.md` first — it's the ground-truth inventory of his
real experience (tools, roles, achievements) and the only source you should
draw from when writing resume content. Read `references/scoring-criteria.md`
before scoring anything — it captures the specific fit lessons learned from
evaluating his last several roles (seniority mismatches and skill gaps are the
two things that most often get missed by a naive keyword match).

## Integration with resume-tailor

When Matthew runs this skill, use the Python utilities to:
1. Load new/unapplied jobs from the resume-tailor database (using `skill_bridge.get_new_jobs()`)
2. After Matthew selects jobs to tailor and applies, mark them as applied in the DB (using `skill_bridge.mark_job_applied(job_id)`)

Skip "Step 1: Search" below — jobs come from resume-tailor's database instead.

## Step 1: Load jobs from resume-tailor database

Always search across all three unless Matthew asks to narrow it:
- **(a) Analytics Engineer** — "Senior Analytics Engineer," "Analytics Engineer"
  roles emphasizing SQL/dbt/warehouse work.
- **(b) Data-focused PM** — Product Manager roles where analytics/BI/data is
  the core of the job, not a side skill.
- **(c) Strategic/data leadership IC** — roles like the Faire "Strategy &
  Analytics Senior Lead" or Broccoli — embedded analytical/BI partner with
  real ownership, senior IC scope.

Location: remote (US), hybrid, or Bay Area on-site are all acceptable — don't
filter any of these out.

Search job boards directly (LinkedIn itself is mostly closed to scraping —
search and read public postings, but don't expect to browse it like a logged-in
user). Good sources: Built In San Francisco (builtinsf.com), Wellfound/Startup
Jobs (startup.jobs, wellfound.com), Y Combinator's Work at a Startup, company
career pages, and general web search for the role titles above + "San
Francisco" / "Bay Area" / "remote." Vary query phrasing per vector — a combined
query returns shallow results for all three, so search each vector separately
(several queries each).

## Step 2: Score each posting

For every posting found, apply `references/scoring-criteria.md`. For each one,
produce:
- Company, title, vector (a/b/c), location/remote status, link
- Fit tier: **Strong fit** / **Worth a look, flag the gap** / **Weak fit**
- 1–2 sentence rationale citing specific language from the JD — the same way
  Broccoli, Aspire, Parafin, and Intuitive were each evaluated in this
  thread. Name the specific mismatch (seniority, a required skill he doesn't
  have, domain) rather than a vague "might not be a fit."

Don't silently drop postings that turn up weak — show them with an honest
score so Matthew can decide, the same way Parafin and Intuitive were still
discussed in full even though they were weaker fits.

## Step 3: Present the shortlist for review

Show results grouped by vector or by fit tier (whichever makes the list
easier to scan), with the link, tier, and rationale for each. Use
`link_preview_display_v0` for the postings if there are external links to
show, or a clear list in prose if that's cleaner for the number of results.
Ask Matthew which ones he wants to move forward on — don't assume; wait for
his reply.

## Step 4: Wait for selection

Matthew will name which postings he wants to apply to. Only proceed to
tailoring for those.

## Step 5: Generate a tailored resume for each selection

For each job Matthew picks:
1. Re-read that specific JD (not a summary of it, not another job's JD in the
   same batch) to identify what to emphasize — the same way past tailoring in
   this thread led with the Promise customer-facing bullet for Broccoli, or
   would lean into cross-functional partnership for a PM role. When tailoring
   several resumes in one batch, do NOT reuse one job's bullet order/skills
   line as a template for another even if their vectors match — two Analytics
   Engineer postings can still emphasize different things (e.g. Zipline's
   "trusted partner to customer/ops teams" vs. BetterUp's "trusted advisor to
   leadership on AI governance") and the skills line and bullet order should
   reflect each JD's actual language, not a shared default.
2. Include ALL SIX roles from `assets/resume_master.md`, every bullet under
   each — this is the established one-page format (confirmed against Faire
   and Broccoli, 13 bullets across 6 roles, still one page). Never drop a
   role or a bullet to save space; only reorder bullets within a role for
   relevance, and lightly rephrase for framing. Never introduce a tool,
   metric, or claim that isn't already in that file. If the JD requires
   something genuinely absent from his background (e.g. Python/ML), say so to
   Matthew rather than quietly working around it or trimming content instead.
3. Write a `spec.json` (see the shape documented at the top of
   `scripts/build_resume.js`) with the tailored summary, skills line, and
   role/bullet selections.
4. Run `node scripts/build_resume.js <spec.json> <output.docx>` to generate
   the docx — this reproduces Matthew's exact resume template (fonts, sizes,
   colors, margins, right-aligned dates, bullet style), so don't hand-roll a
   new docx-js script from scratch.
5. Convert to PDF with LibreOffice (`soffice --headless --convert-to pdf`) and
   render it to an image to visually check it's one page and correctly
   formatted before sharing — the same verification step used earlier in this
   thread caught a page-count regression.
6. Save both docx and pdf to the outputs directory using the filename
   `Matthew Pennisi - Resume <Month Year> (<Company>).docx` /
   `.pdf` (e.g. `Matthew Pennisi - Resume Aug 2026 (Zipline).docx`), where
   <Month Year> is the current month/year and <Company> is the company name
   as it appears in the job posting. Present docx+pdf together per company.

Keep each tailored resume to one page, matching the established template.

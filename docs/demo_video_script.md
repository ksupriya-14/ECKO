# Demo Video Script (3–5 minutes)

I can't generate a video file directly, but everything below is built and
tested — record your screen following this script and it'll cover every
point the assignment asks for.

## Suggested recording flow

**0:00–0:30 — Frame the problem**
"Eko runs on a network of micro-entrepreneur partners. Every week, field
managers manually scan spreadsheets to figure out who needs a call, who's
at risk, who's ready for a limit upgrade. This AI Worker owns that triage
step end-to-end."

**0:30–1:00 — Show the goal/system definition**
Open `README.md`, scroll through Goal / User / System / Constraints /
Definition of Done sections. Say: "Before writing any code I defined what
'done' means for this workflow — not just 'it ran,' but a specific
checklist covering completeness, checks, audit, and escalation."

**1:00–1:45 — Show the input data**
Open `data/sample_input.csv`. Point out it's 28 partners, and mention:
"I deliberately broke 6 of these rows on purpose — missing data, a broken
total, a negative value, a compliance conflict, a duplicate ID, and a
brand-new partner with no history — because a real system has to survive
dirty data, not just clean demo data."

**1:45–3:00 — Run it live**
```bash
cd src
python3 worker.py --input ../data/sample_input.csv --outdir ../output --logdir ../logs
```
Then open, in order:
1. `output/validation_report.md` — "here's every data issue it caught,
   row by row."
2. `output/human_review_queue.csv` — "here's exactly what got escalated
   and why — nothing gets silently guessed."
3. `output/partner_classification_output.csv` — "here's the full
   classification for every clean partner, with a reason and confidence
   for each."
4. `output/summary_report.md` — "and here's the manager-facing rollup —
   this is the one page they'd actually read."

**3:00–3:45 — Zoom in on ONE failure case**
Pick the KYC-rejected-but-active partner (`1024`). Show the row in the raw
CSV, then show it in `human_review_queue.csv` with the reason. Say: "This
is the highest-stakes example — a partner with rejected KYC still doing
350 transactions. The worker never lets good transaction numbers override
a compliance flag. It escalates, every time, no exceptions."

**3:45–4:15 — Audit trail**
Open `logs/audit_log.csv`. "Every decision — every flag, every
classification, every escalation — is timestamped and logged. This is what
makes it usable in a real business process, not just a notebook demo."

**4:15–4:45 — Wrap up**
"Current version uses transparent rule-based logic so every decision is
explainable to a manager or compliance reviewer in one sentence. Next
version: train on manager agree/disagree feedback to refine the thresholds,
and add region-aware baselines so growth expectations aren't one-size-fits-all."

## Recording tips
- Use a terminal + file viewer split screen (VS Code works well: left pane
  file tree, right pane terminal).
- Actually run the command live rather than showing pre-made output — it
  reinforces that this is a working prototype, not a mockup.
- Keep each report open in its own tab so you can flip between them quickly.

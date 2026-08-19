# Micro-Entrepreneur Performance Worker

An AI Worker that owns one bounded workflow end-to-end: turning raw partner
(agent / retailer) activity data into a classified, action-ready performance
review — the kind of weekly review a field operations team at Eko would run
across its micro-entrepreneur network.

This directly reflects Eko's business: Eko runs on a network of retail
partners/agents who provide banking and payment services to end customers.
Managing which partners are thriving, struggling, or at risk is a recurring,
high-volume operational workflow — exactly the kind of bounded, rules-plus-
judgment task an AI Worker should own.

---

## 1. Goal

Classify each micro-entrepreneur partner's performance over the last 30 days
and recommend one concrete next action per partner, so field/ops managers
spend their limited time on the partners who actually need intervention
instead of manually reviewing every row of a spreadsheet.

## 2. User

Field operations managers and relationship managers who run weekly partner
reviews and decide who gets a retention call, an incentive upgrade, a
compliance check, or a reactivation nudge.

## 3. System (where this sits in the bigger picture)

Part of Eko's **Partner Network Management** workflow:

```
Transaction/CRM systems → [THIS WORKER: validate → classify → recommend]
    → Manager dashboard / weekly review meeting → Field action (call, incentive,
      compliance escalation, deactivation review) → outcome logged back →
      feedback loop into next run
```

The worker does not replace the manager. It replaces the manual triage step
that currently eats the first hour of every review meeting.

## 4. Inputs

One CSV (or equivalent table) per run, one row per partner, with:
transaction counts/volume for the current and prior 30-day windows, active
days, complaints, service uptime, KYC status, onboarding date, and two GTV
figures (declared total vs. sum of daily logs) used to cross-check data
integrity. Full field list: `docs/data_dictionary_and_assumptions.md`.

## 5. Decisions the worker can make

- Classify each partner as **Active, Inactive, Improving, Declining, Risky,
  or High-Potential** (or a clearly-labeled "insufficient history" case for
  brand-new partners).
- Recommend one next action per partner (see `src/worker.py:classify_partner`
  for the exact rule set).
- Decide, per partner, whether it has **enough clean data to decide at all**
  — and if not, escalate instead of guessing.

## 6. Outputs

Per run (`output/`):
- `partner_classification_output.csv` — one row per partner: classification,
  recommended action, confidence, reasoning, any data issues found.
- `human_review_queue.csv` — subset that needs a human decision, with reasons.
- `validation_report.md` — every data-quality issue found, row by row.
- `summary_report.md` — manager-facing rollup: counts by class, escalation
  list, and a "how do I know this run succeeded" checklist.
- `logs/audit_log.csv` — append-only, timestamped decision trail.

## 7. Constraints (what it must NOT do)

- Never auto-deactivate, suspend, or financially penalize a partner.
- Never make a compliance/fraud determination (KYC issues are always
  escalated, never resolved automatically).
- Never disburse incentives or payouts.
- Never contact a customer or partner directly (it produces recommendations
  for a human to act on, not automated outreach).
- Never classify a partner using incomplete or internally-inconsistent data —
  it escalates instead of filling gaps with assumptions.
- Never silently drop a row without logging why.

## 8. Definition of Done

A run is complete only when **all** of the following hold:

**Output produced**
- [ ] `partner_classification_output.csv` exists and has exactly one row per
      unique, valid `partner_id` present in the input.
- [ ] `human_review_queue.csv` exists (even if empty).
- [ ] `validation_report.md` and `summary_report.md` exist and are non-empty.
- [ ] `logs/audit_log.csv` has at least one entry per partner_id processed.

**Completeness**
- [ ] Every row in the classification output has a non-null `classification`,
      `recommended_action`, and `confidence` value.
- [ ] Every dropped or flagged input row is accounted for in the validation
      report — the row counts must reconcile: `input rows = output rows +
      duplicates dropped` (duplicates are the only rows removed; everything
      else with issues is escalated, not deleted).

**Checks that must pass**
- [ ] Schema check: all required columns present, or the run aborts loudly
      instead of producing a partial/garbage output.
- [ ] Every row has passed the validation rules (missing fields, negative
      values, out-of-range values, GTV arithmetic consistency, KYC/activity
      conflict, duplicate IDs) — pass or explicit flag, no silent skips.
- [ ] Confidence threshold check: any classification below 0.55 confidence is
      routed to human review rather than shipped as a final answer.

**Information captured in the final report**
- [ ] Reasoning for every classification (not just the label).
- [ ] A clear count and list of what was escalated and why.
- [ ] A reconciliation statement a manager can use to trust the run without
      re-checking the raw data themselves.

**Failure/exception handling**
- [ ] Missing critical fields → escalate, never impute/guess.
- [ ] Broken totals (declared vs. computed GTV mismatch beyond 2% tolerance)
      → escalate, flagged as a data-integrity issue.
- [ ] Invalid values (negative volumes, uptime >100%) → escalate.
- [ ] KYC-not-verified but transacting → escalate as compliance risk, always,
      regardless of transaction volume.
- [ ] Duplicate partner_id with conflicting data → escalate both rows rather
      than silently keeping one.
- [ ] New partner with no prior-period baseline → labeled explicitly as
      "insufficient history," never silently treated as 0% or 100% growth.
- [ ] Unreadable input file / missing required columns → hard abort with a
      logged reason, no partial output presented as if complete.

**Logged for audit**
- [ ] Every validation flag, every classification decision, and every
      escalation, each with a timestamp, partner_id, stage, and reason.

**Escalated to a human**
- [ ] See Section 10 below — escalation criteria are enforced automatically,
      not left to manager discretion after the fact.

**Success signal for the user**
- [ ] The top of `summary_report.md` states total partners processed, how
      many were escalated, and a plain-English "how to confirm this run
      completed successfully" section — no need to inspect code or logs to
      trust the run.

## 9. Completion checklist (operational, per run)

1. Input file loads and schema matches expected columns → else abort.
2. Row count in = row count out + duplicates dropped (reconciled).
3. No partner has a null classification.
4. Every escalated row has a stated reason.
5. Audit log row count ≥ number of partners processed.
6. Summary report generated and includes the escalation list.
7. Manager can open `summary_report.md` alone and know what to do next.

## 10. Escalation criteria (send to a human, don't decide automatically)

The worker escalates a partner rather than classifying automatically when
**any** of the following are true:
- A required field for classification is missing or unparseable.
- Declared vs. computed GTV disagree by more than 2%.
- Any numeric field is out of its valid physical range (negative volume,
  uptime outside 0–100%).
- KYC status is not "Verified" while the partner is actively transacting.
- The same `partner_id` appears more than once with conflicting data.
- Model confidence in the classification falls below 0.55 (e.g., partners
  right on a classification boundary, or with unusual combinations of
  signals the rules weren't confidently designed for).
- Complaint volume is extreme (≥5 in 30 days) even though it's already
  correctly labeled "Risky" — high-complaint cases get a human, not just a
  label.

Everything that is escalated lands in `human_review_queue.csv` with the
specific reason, so a manager doesn't need to re-derive why it was flagged.

## 11. Feedback loop

Each classification carries a `confidence` score and a machine-readable
`reasoning` string. The intended production loop (not simulated in this
prototype, but designed for):
1. Managers mark each classification/action as **Agree / Disagree** with an
   optional free-text correction, logged to a `feedback_log.csv` keyed by
   `partner_id` + `run_id`.
2. Weekly, disagreements are reviewed for patterns (e.g., "growth ≥ 20% is
   too aggressive a bar for High-Potential in low-GTV regions") and the
   relevant threshold constant in `worker.py` (e.g., `GTV_TOLERANCE_PCT`, the
   0.5/0.2/-0.2 growth cutoffs, the 0.55 confidence gate) is adjusted.
3. Every threshold change is itself logged (old value, new value, reason,
   date, approver) so classification logic changes are auditable the same
   way individual decisions are.
4. Recurring escalation reasons (e.g., a data source that frequently sends
   broken totals) get raised as a data-pipeline fix upstream, not just
   patched around every run.

## 12. What the current version can do

- Validates a partner activity file for structural, range, arithmetic, and
  compliance issues before making any decision.
- Classifies partners into 6 categories using explainable, auditable rules
  (not a black-box model), each with a stated confidence and written reason.
- Correctly separates "no growth data yet" (new partner) from "0% growth"
  (stable partner) — a common correctness bug in naive versions of this kind
  of logic.
- Produces manager-ready and audit-ready outputs without any manual cleanup.
- Demonstrably fails safely: see `docs/failure_scenario.md` for a walkthrough
  of every intentional bad row in the sample data and exactly how the worker
  handled each one.

## 13. What would improve in the next version

- Replace fixed rule thresholds with a lightweight model (e.g., logistic
  regression or gradient-boosted trees) trained on manager Agree/Disagree
  feedback, while keeping the rule-based escalation gates as hard guardrails
  around it (the model should never override a compliance or data-integrity
  escalation).
- Add trend visualization (multi-period history, not just current vs. prior
  30 days) so "Improving" vs. "Declining" isn't a single-window judgment.
- Add a region/segment-aware baseline (a 20% growth threshold may be
  unrealistic in a saturated urban region vs. easy in a newly-launched rural
  one).
- Real feedback_log.csv wiring into a scheduled retraining/threshold-review
  job instead of a manual quarterly review.
- Deduplication logic that can reconcile conflicting duplicate rows
  automatically when the conflict is trivial (e.g., only a timestamp differs)
  rather than always escalating — currently it escalates all conflicting
  duplicates, which is safe but not maximally efficient.

---

## Repository layout

```
.
├── README.md
├── requirements.txt
├── .gitignore
├── docs/
│   ├── data_dictionary_and_assumptions.md
│   ├── failure_scenario.md
│   ├── demo_video_script.md
│   └── API_DOCUMENTATION.md
├── data/
│   └── sample_input.csv
├── src/
│   ├── worker.py
│   ├── generate_sample_data.py
│   ├── verify.py
│   └── api.py
├── output/
│   ├── partner_classification_output.csv
│   ├── human_review_queue.csv
│   ├── validation_report.md
│   └── summary_report.md
├── logs/
│   └── audit_log.csv
├── demo_notebook.ipynb
└── partner_performance_workbook.xlsx
```

## How to run it yourself

### Option 1: Command Line

```bash
# Install dependencies
pip install -r requirements.txt

# Generate sample data (optional)
python src/generate_sample_data.py

# Run the worker
python src/worker.py --input data/sample_input.csv --outdir output --logdir logs

# Verify the results
python src/verify.py --input data/sample_input.csv --outdir output --logdir logs
```

### Option 2: Web API

```bash
# Start the API server
python src/api.py

# Open the web interface in your browser
# Navigate to: http://localhost:8000/interface

# Or use the API programmatically (see docs/API_DOCUMENTATION.md)
```

### Option 3: Jupyter Notebook

```bash
# Install Jupyter if not already installed
pip install jupyter

# Open the demo notebook
jupyter notebook demo_notebook.ipynb
```

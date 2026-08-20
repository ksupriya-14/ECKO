# Micro-Entrepreneur Performance Worker

> **An AI Worker for Eko-style partner performance monitoring and weekly operational review.**

The **Micro-Entrepreneur Performance Worker** owns one bounded workflow end-to-end: it converts raw partner/retailer activity data into a **validated, classified, explainable, and action-ready performance review**.

The worker is designed around a recurring field-operations problem: managers should not have to manually inspect every partner record before deciding who needs attention.

---

## 1. Project Overview

### Problem

Eko operates through a network of retail partners/agents who provide banking and payment services to end customers. Managing a large partner network requires recurring decisions about:

- Which partners are performing well?
- Which partners are inactive or declining?
- Which partners may have high potential?
- Which partners require intervention?
- Which records should **not** be decided automatically because the data is unreliable or sensitive?

The worker automates the **manual triage step** while keeping the final operational decision with a human manager.

### Solution

The worker follows a controlled pipeline:

**Raw Partner Data → Validation → Data Integrity Checks → Performance Classification → Action Recommendation → Confidence Check → Human Escalation → Reports & Audit Log**

---

# 2. Goal

Classify each micro-entrepreneur's performance over the last **30 days** and recommend **one concrete next action per partner**.

The goal is to help field/operations managers focus their limited time on partners who actually need intervention instead of manually reviewing every spreadsheet row.

---

# 3. User

### Primary Users

- Field Operations Managers
- Relationship Managers

### How they use it

Managers can use the weekly output to decide whether a partner needs:

- Retention call
- Incentive upgrade
- Compliance check
- Reactivation nudge
- Human review/escalation

> **Important:** The worker recommends actions; it does not take those actions automatically.

---

# 4. Where This Fits in the Business Workflow

The worker is part of the **Partner Network Management** workflow.

```text
┌──────────────────────────────┐
│ Transaction / CRM Systems    │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│ Partner Activity CSV / Data  │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│ 1. INPUT & SCHEMA VALIDATION │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│ 2. DATA QUALITY & INTEGRITY  │
│    - Missing values          │
│    - Invalid ranges          │
│    - Duplicate IDs           │
│    - GTV consistency         │
│    - KYC/activity conflicts  │
└──────────────┬───────────────┘
               │
        ┌──────┴──────┐
        │             │
     Invalid        Valid
        │             │
        ▼             ▼
┌───────────────┐  ┌─────────────────────────┐
│ Human Review  │  │ 3. PERFORMANCE ANALYSIS │
│ / Escalation  │  └────────────┬────────────┘
└───────┬───────┘               │
        │                       ▼
        │             ┌─────────────────────────┐
        │             │ 4. CLASSIFICATION       │
        │             │ Active / Inactive       │
        │             │ Improving / Declining   │
        │             │ Risky / High-Potential  │
        │             │ Insufficient History    │
        │             └────────────┬────────────┘
        │                          │
        │                          ▼
        │             ┌─────────────────────────┐
        │             │ 5. ACTION RECOMMENDATION│
        │             └────────────┬────────────┘
        │                          │
        │                          ▼
        │             ┌─────────────────────────┐
        │             │ 6. CONFIDENCE CHECK     │
        │             │ < 0.55 → Human Review   │
        │             └────────────┬────────────┘
        │                          │
        └──────────────┬───────────┘
                       ▼
┌──────────────────────────────────────────┐
│ 7. OUTPUT & REPORTING                    │
│ Classification + Action + Reasoning      │
│ Validation Report + Summary + Audit Log  │
└───────────────────┬──────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────┐
│ Manager Dashboard / Weekly Review        │
└───────────────────┬──────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────┐
│ Human Field Action                       │
│ Call / Incentive / Compliance / React.   │
└───────────────────┬──────────────────────┘
                    │
                    ▼
             Feedback / Outcome
                    │
                    └──────────► Next Run
```

### Key Design Principle

The worker **does not replace the manager**.

It replaces the repetitive **manual triage step** before the weekly review.

---

# 5. End-to-End AI Worker Workflow

## Step 1 — Ingest

Read one partner activity file per run.

Each row represents one partner.

## Step 2 — Validate

Check:

- Required columns
- Missing values
- Numeric values
- Valid ranges
- Duplicate `partner_id`
- GTV arithmetic consistency
- KYC/activity conflicts

If the input file is unreadable or required columns are missing, the run **aborts loudly** instead of producing partial output.

## Step 3 — Check Data Integrity

The worker compares:

**Declared GTV vs. computed GTV from daily logs**

A mismatch greater than **2%** is treated as a data-integrity issue and escalated.

## Step 4 — Analyze Performance

The worker uses current and prior 30-day activity to understand partner performance.

Signals include:

- Transaction counts
- Transaction volume
- Active days
- Complaints
- Service uptime
- KYC status
- Onboarding date
- Growth/change between periods

## Step 5 — Classify Partner

A partner can be classified as:

| Classification | Meaning |
|---|---|
| **Active** | Partner is actively performing |
| **Inactive** | Partner has low/no recent activity |
| **Improving** | Performance trend is improving |
| **Declining** | Performance trend is declining |
| **Risky** | Risk-related signals require attention |
| **High-Potential** | Strong performance/growth indicates potential |
| **Insufficient History** | New partner does not have a prior-period baseline |

The exact rule set is implemented in `src/worker.py`.

## Step 6 — Recommend One Action

For every valid classification, the worker recommends one concrete next action for the manager.

The recommendation is accompanied by:

- Confidence
- Reasoning
- Data issues, if any

## Step 7 — Confidence Gate

If confidence is **below 0.55**, the worker does not ship the decision as final.

Instead:

```text
Confidence < 0.55
        ↓
Human Review Queue
        ↓
Manager Decision
```

## Step 8 — Generate Outputs

The worker produces manager-facing and audit-facing files.

## Step 9 — Audit

Every validation flag, classification, escalation, and decision is timestamped and logged.

## Step 10 — Feedback Loop

Managers can mark a result:

```text
Agree / Disagree
      ↓
Feedback Log
      ↓
Review recurring patterns
      ↓
Adjust thresholds / improve logic
      ↓
Next weekly run
```

---

# 6. Inputs

One CSV (or equivalent table) per run, with one row per partner.

Expected information includes:

- `partner_id`
- Current 30-day transaction counts/volume
- Prior 30-day transaction counts/volume
- Active days
- Complaints
- Service uptime
- KYC status
- Onboarding date
- Declared GTV
- Computed/summed GTV from daily logs

The complete field definition is documented in:

`docs/data_dictionary_and_assumptions.md`

---

# 7. Decision & Escalation Logic

The worker follows a **rules + judgment** approach with hard safety gates.

```text
                 Partner Record
                       │
                       ▼
              Required Data Valid?
                /            \
              NO              YES
              │                │
              ▼                ▼
        HUMAN REVIEW      Integrity Checks
                              │
                    ┌─────────┴─────────┐
                    │                   │
                 Issue               Clean
                    │                   │
                    ▼                   ▼
             HUMAN REVIEW       Performance Rules
                                        │
                                        ▼
                                  Classification
                                        │
                                        ▼
                                  Recommendation
                                        │
                                        ▼
                               Confidence ≥ 0.55?
                                  /          \
                                NO            YES
                                │              │
                                ▼              ▼
                         HUMAN REVIEW      Final Output
```

### Mandatory Escalation Conditions

A partner is escalated when **any** of these conditions is true:

1. Required classification field is missing/unparseable.
2. Declared vs. computed GTV differs by more than **2%**.
3. Numeric value is outside the valid range.
4. KYC is not `Verified` while the partner is actively transacting.
5. Duplicate `partner_id` contains conflicting data.
6. Classification confidence is below **0.55**.
7. Complaint volume is **5 or more in 30 days**, even if classified as Risky.
8. The partner is new and has no prior-period baseline.
9. The input file is unreadable or required columns are missing.

---

# 8. Outputs

Every run generates:

| Output | Purpose |
|---|---|
| `partner_classification_output.csv` | Classification, action, confidence, reasoning and data issues for each partner |
| `human_review_queue.csv` | Partners requiring human review |
| `validation_report.md` | Detailed data-quality issues |
| `summary_report.md` | Manager-facing run summary |
| `logs/audit_log.csv` | Timestamped audit trail |

### Example Output Flow

```text
Partner ID
    ↓
Classification
    ↓
Recommended Action
    ↓
Confidence
    ↓
Reasoning
    ↓
Escalation? ── Yes ──► Human Review Queue
    │
    No
    ↓
Manager Review
```

---

# 9. Example Manager View

A manager should be able to understand the result without opening the raw dataset.

```text
Weekly Partner Performance Review
──────────────────────────────────

Total Partners Processed: 100
Escalated for Review: 12

High-Potential: 18
Improving:      24
Active:         31
Declining:      15
Inactive:        7
Risky:           3
Insufficient:    2

Priority:
→ Review high-complaint partners
→ Review KYC/activity conflicts
→ Contact declining partners
→ Follow up with high-potential partners
```

The actual numbers above are illustrative; the generated `summary_report.md` contains the run-specific values.

---

# 10. Constraints & Safety Guardrails

The worker **must NOT**:

- Auto-deactivate a partner.
- Suspend a partner.
- Financially penalize a partner.
- Make a compliance/fraud determination.
- Resolve KYC issues automatically.
- Disburse incentives or payouts.
- Contact customers or partners directly.
- Classify partners using incomplete/inconsistent data.
- Silently drop input rows.
- Fill critical missing information by guessing.

### Human-in-the-Loop Principle

```text
AI Worker
   │
   ├── Can validate
   ├── Can classify
   ├── Can recommend
   └── Can escalate
          │
          ▼
     Human Manager
          │
          └── Makes final operational decision
```

---

# 11. Definition of Done

A run is considered complete only when all of the following are satisfied.

### Outputs

- [ ] `partner_classification_output.csv` exists.
- [ ] Exactly one output row exists per unique valid `partner_id`.
- [ ] `human_review_queue.csv` exists, even if empty.
- [ ] `validation_report.md` is generated and non-empty.
- [ ] `summary_report.md` is generated and non-empty.
- [ ] `logs/audit_log.csv` contains an entry for each processed partner.

### Completeness

- [ ] Every classification has a classification value.
- [ ] Every classification has a recommended action.
- [ ] Every classification has a confidence value.
- [ ] Every flagged/dropped row is accounted for.
- [ ] Row reconciliation is maintained:

```text
Input Rows = Output Rows + Duplicates Dropped
```

Duplicates are the only rows removed; other problematic rows are escalated.

### Validation

- [ ] Required schema is present.
- [ ] Missing fields are checked.
- [ ] Negative values are checked.
- [ ] Out-of-range values are checked.
- [ ] GTV consistency is checked.
- [ ] KYC/activity conflicts are checked.
- [ ] Duplicate IDs are checked.
- [ ] Low-confidence classifications are escalated.

### Auditability

- [ ] Every validation flag is logged.
- [ ] Every classification decision is logged.
- [ ] Every escalation is logged.
- [ ] Logs contain timestamp, `partner_id`, stage and reason.

### Manager Success Signal

The top of `summary_report.md` should clearly state:

- Total partners processed
- Number escalated
- Why they were escalated
- How the manager can confirm that the run completed successfully

---

# 12. Failure & Exception Handling

| Failure | Worker Response |
|---|---|
| Missing critical field | Escalate |
| GTV mismatch > 2% | Escalate |
| Negative volume | Escalate |
| Uptime outside 0–100% | Escalate |
| KYC not verified + active transactions | Escalate |
| Conflicting duplicate ID | Escalate both rows |
| New partner with no baseline | `Insufficient History` |
| Unreadable file | Hard abort |
| Missing required columns | Hard abort |
| Confidence < 0.55 | Human review |
| Complaints ≥ 5 in 30 days | Human review |

The worker is designed to **fail safely rather than guess**.

---

# 13. Feedback Loop

The prototype is designed for a future manager-feedback workflow.

```text
Classification
      ↓
Manager
      ↓
Agree / Disagree
      ↓
feedback_log.csv
      ↓
Weekly Pattern Review
      ↓
Threshold / Rule Improvement
      ↓
Next Run
```

Examples of parameters that may be reviewed include:

- `GTV_TOLERANCE_PCT`
- Growth thresholds
- `0.55` confidence gate

Any threshold change should be logged with:

- Old value
- New value
- Reason
- Date
- Approver

Recurring data-quality problems should be fixed upstream where possible instead of repeatedly patched during each run.

---

# 14. Current Version

The current implementation:

- Validates structural, range, arithmetic and compliance-related issues before making decisions.
- Classifies partners into six operational categories using explainable, auditable rules.
- Provides confidence and written reasoning.
- Separates **no growth history** from **0% growth**.
- Produces manager-ready and audit-ready outputs.
- Demonstrates safe failure handling for intentionally bad sample records.

See:

`docs/failure_scenario.md`

for the sample failure walkthrough.

---

# 15. Future Improvements

Possible next-version improvements:

### 1. Lightweight ML Model

Replace or augment fixed classification thresholds with a lightweight model such as:

- Logistic Regression
- Gradient-Boosted Trees

Manager feedback would become training/evaluation data.

**Important:** hard escalation rules should remain guardrails around the model.

### 2. Multi-Period Trend Analysis

Use more than one current/prior 30-day window to make Improving vs. Declining decisions more robust.

### 3. Region/Segment-Aware Baselines

Performance thresholds could account for regional or segment differences.

### 4. Automated Feedback Pipeline

Connect `feedback_log.csv` to a scheduled threshold-review or retraining workflow.

### 5. Smarter Deduplication

Future versions could reconcile duplicates when the conflict is trivial, while still escalating genuinely conflicting records.

---

# 16. Repository Structure

```text
Micro-Entrepreneur-Performance-Worker/
│
├── README.md
├── requirements.txt
├── .gitignore
│
├── docs/
│   ├── data_dictionary_and_assumptions.md
│   ├── failure_scenario.md
│   ├── demo_video_script.md
│   └── API_DOCUMENTATION.md
│
├── data/
│   └── sample_input.csv
│
├── src/
│   ├── worker.py
│   ├── generate_sample_data.py
│   ├── verify.py
│   └── api.py
│
├── output/
│   ├── partner_classification_output.csv
│   ├── human_review_queue.csv
│   ├── validation_report.md
│   └── summary_report.md
│
├── logs/
│   └── audit_log.csv
│
├── demo_notebook.ipynb
└── partner_performance_workbook.xlsx
```

---

# 17. How to Run

## Option 1 — Command Line

### Install dependencies

```bash
pip install -r requirements.txt
```

### Generate sample data

```bash
python src/generate_sample_data.py
```

### Run the worker

```bash
python src/worker.py --input data/sample_input.csv --outdir output --logdir logs
```

### Verify the run

```bash
python src/verify.py --input data/sample_input.csv --outdir output --logdir logs
```

---

## Option 2 — Web API

Start the API:

```bash
python src/api.py
```

Open:

```text
http://localhost:8000/interface
```

API details are available in:

`docs/API_DOCUMENTATION.md`

---

## Option 3 — Jupyter Notebook

Install Jupyter:

```bash
pip install jupyter
```

Run:

```bash
jupyter notebook demo_notebook.ipynb
```

---

# 18. Quick Start Workflow

For a new user, the shortest path is:

```text
1. Install dependencies
        ↓
2. Generate / provide input CSV
        ↓
3. Run worker.py
        ↓
4. Run verify.py
        ↓
5. Open summary_report.md
        ↓
6. Check human_review_queue.csv
        ↓
7. Review partner_classification_output.csv
        ↓
8. Inspect audit_log.csv when needed
```

---

# 19. What Makes This an AI Worker?

This project is intentionally designed as a **bounded AI Worker**, not a generic chatbot.

It has:

| Worker Component | Implementation |
|---|---|
| **Goal** | Improve partner performance review |
| **User** | Field/Relationship Managers |
| **Input** | Partner activity data |
| **Reasoning** | Validation + explainable rules |
| **Decision** | Performance classification |
| **Action** | Recommended next step |
| **Safety** | Hard escalation gates |
| **Human Control** | Human review queue |
| **Output** | CSV + reports + audit logs |
| **Feedback** | Manager Agree/Disagree loop |
| **Completion** | Definition-of-Done checks |

---

# 20. One-Line Summary

> **The Micro-Entrepreneur Performance Worker turns raw partner activity data into a validated, explainable weekly performance review, prioritizing human attention while keeping sensitive and uncertain decisions under human control.**

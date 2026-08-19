# 🎤 Project Explanation Guide
## How to Present the ECKO Micro-Entrepreneur Performance Worker

---

## 1. Start With the Business Problem (30 seconds)

> **"Eko operates a network of thousands of retail partners — agents and retailers who provide banking and payment services to end customers across India. Every week, the field operations team needs to review which partners are performing well, which are declining, who is risky, and who needs intervention. Currently, this is done manually — someone opens a spreadsheet, eyeballs the numbers, and decides. This doesn't scale."**

**Key point:** You're not building a chatbot or dashboard. You're building an **AI Worker** — an automated system that owns this entire review workflow end-to-end.

---

## 2. What Does the Worker Actually Do? (1 minute)

> **"My AI Worker takes a CSV file of partner activity data and does 4 things automatically:"**

```
CSV Input → [1. VALIDATE] → [2. CLASSIFY] → [3. ESCALATE] → [4. REPORT]
```

| Step | What Happens | Example |
|---|---|---|
| **1. Validate** | Checks for missing fields, negative values, broken totals, duplicate IDs, out-of-range values, KYC conflicts | "Partner 1022 declared ₹5L GTV but daily logs sum to ₹2.1L — that's a 58% mismatch" |
| **2. Classify** | Assigns each partner one of 6 labels: Active, Inactive, Improving, Declining, Risky, High-Potential | "Partner grew GTV by 60% with 400+ transactions → High-Potential" |
| **3. Escalate** | Routes anything it can't safely decide to a human review queue | "Partner has rejected KYC but 350 transactions — compliance risk, sending to human" |
| **4. Report** | Generates 5 output files: classification CSV, review queue, summary report, validation report, audit log | "Manager opens summary_report.md and knows exactly what to do" |

---

## 3. The 6 Classification Labels (30 seconds)

> **"Every partner gets classified into exactly one of these:"**

| Label | Meaning | Recommended Action |
|---|---|---|
| **Active** | Stable performance, GTV change within ±20% | No action needed, continue monitoring |
| **Inactive** | Zero transactions or zero active days | Trigger reactivation outreach call |
| **Improving** | GTV grew ≥20% month-over-month | Offer cross-sell, sustain momentum |
| **Declining** | GTV dropped ≥20% month-over-month | Proactive retention call within 7 days |
| **Risky** | ≥3 complaints OR uptime below 80% | Escalate to field quality team |
| **High-Potential** | GTV grew ≥50% + 200+ txns + 20+ active days | Fast-track for higher limits, assign relationship manager |

> **"There's also a 7th edge case — 'Active (New, insufficient history)' — for brand new partners with no prior-period data. Instead of guessing their growth rate, I explicitly label them as new."**

---

## 4. The Smart Part: What Happens When Data is Bad (1 minute)

> **"This is what separates a good AI Worker from a bad one. My worker has 7 intentional failure scenarios built into the sample data. Let me walk you through them:"**

| # | Problem | What Bad Code Would Do | What My Worker Does |
|---|---|---|---|
| 1 | **Missing fields** (txn count, volume blank) | Crash, or fill with 0 and misclassify | Escalates with reason: "3 critical fields missing" |
| 2 | **Broken totals** (declared ₹5L vs computed ₹2.1L) | Silently pick one number | Escalates: "58% mismatch exceeds 2% tolerance" |
| 3 | **Negative volume** (-₹50,000) | Use `abs()` and hide the bug | Escalates: "volume can't be negative — pipeline bug" |
| 4 | **KYC Rejected but transacting** | Classify normally based on numbers | **Always escalates** — compliance risk overrides performance |
| 5 | **Duplicate partner ID** (exact copy) | Keep both, double-count | Deduplicates safely, logs it |
| 6 | **Uptime 143%** (impossible value) | Use it in calculations | Escalates: "uptime can't exceed 100%" |
| 7 | **New partner, no prior data** | Divide by zero, or treat as 0% growth | Labels as "New, insufficient history" with low confidence |

> **"21% of my sample data is intentionally dirty. The worker handled every case correctly — nothing crashed, nothing was silently wrong."**

---

## 5. The Escalation Logic (30 seconds)

> **"The worker will NEVER guess. If it's not confident, it sends to a human."**

7 automatic escalation triggers:
1. Missing critical fields
2. Broken totals (declared vs computed GTV > 2% difference)
3. Negative or out-of-range values
4. KYC not verified + active transactions
5. Duplicate partner IDs with conflicting data
6. Confidence score below 0.55 threshold
7. Extreme complaints (≥5 in 30 days)

> **"Each escalated partner goes into `human_review_queue.csv` with the exact reason — the manager doesn't need to re-investigate."**

---

## 6. The Verification Layer (30 seconds)

> **"I don't just trust that the worker ran correctly. I built a separate verification harness that independently checks the outputs — like a QA reviewer."**

15 verification checks:
- Row reconciliation (input = output + dupes dropped)
- No null classifications
- Every escalated row has a reason
- Confidence threshold enforced
- Known failure cases were actually caught
- KYC-conflict never got a positive label
- Audit log covers every partner
- Reports are non-empty

> **"All 15/15 pass. You can run `python verify.py` yourself to confirm."**

---

## 7. The Audit Trail (20 seconds)

> **"Every single decision the worker makes is logged with a timestamp, partner ID, stage, and reason."**

```
timestamp | partner_id | stage          | decision              | reason                    | severity
2026-08-17| 1024       | validation     | flag_compliance_risk  | kyc_status=Rejected       | error
2026-08-17| 1024       | classification | escalate              | Blocking data issue(s)... | error
```

> **"If someone asks 'why was Partner 1024 escalated?' — the answer is right there in the audit log."**

---

## 8. Definition of Done (30 seconds)

> **"I defined what 'done' means before writing any code:"**

✅ Output: 5 files produced (classification, review queue, validation report, summary report, audit log)
✅ Completeness: Every partner has a classification, action, confidence — no nulls
✅ Reconciliation: Input rows = output rows + duplicates dropped
✅ Checks: 15 independent verification checks all pass
✅ Failures handled: 7 types of bad data handled correctly
✅ Escalation: Automatic, rule-based, with stated reasons
✅ Audit: Every decision logged
✅ User signal: Summary report tells the manager "here's how you know this run succeeded"

---

## 9. Architecture & Tech Stack (20 seconds)

```
┌─────────────────────────────────────────────────┐
│                    Frontend                      │
│  Dark-theme dashboard · Chart.js · Drag & Drop  │
│  Stats cards · Verification panel · Downloads    │
└──────────────────────┬──────────────────────────┘
                       │ HTTP POST /upload
┌──────────────────────▼──────────────────────────┐
│              FastAPI Backend (api.py)             │
│  Upload handler · CORS · File management         │
└──────────┬───────────────────────┬───────────────┘
           │                       │
┌──────────▼──────────┐ ┌─────────▼───────────────┐
│   Worker Pipeline    │ │   Verification Harness   │
│   (worker.py)        │ │   (verify.py)            │
│                      │ │                          │
│  Validate → Classify │ │  15 independent checks   │
│  → Escalate → Report │ │  on the worker's output  │
└──────────────────────┘ └──────────────────────────┘
```

| Component | Technology |
|---|---|
| Backend | Python, FastAPI, Uvicorn |
| Data | Pandas, NumPy |
| Frontend | HTML/CSS/JS, Chart.js |
| Validation | Custom rule engine |
| Verification | Independent test harness |
| Design | Dark theme, Inter font, glassmorphism |

---

## 10. What the Worker Does NOT Do (Important!)

> **"Constraints are as important as capabilities:"**

❌ Never auto-deactivates or suspends a partner
❌ Never makes compliance/fraud determinations
❌ Never disburses incentives or payouts
❌ Never contacts a partner or customer directly
❌ Never classifies with incomplete data — escalates instead
❌ Never silently drops a row without logging why

> **"It's a decision-support system, not a decision-execution system. It recommends — humans act."**

---

## 11. Feedback Loop Design (20 seconds)

> **"The current version doesn't implement feedback, but it's designed for it:"**

1. Manager marks each classification as **Agree/Disagree**
2. Weekly, disagreements are reviewed for patterns
3. Thresholds in the code (like the 20% growth cutoff) get adjusted
4. Every threshold change is itself logged and auditable

> **"This is how the worker would improve over time — not by retraining a black-box model, but by adjusting transparent, auditable thresholds based on manager feedback."**

---

## 12. What I'd Improve in V2

1. **ML model** for classification (trained on manager feedback), with rule-based escalation as hard guardrails
2. **Multi-period trends** (not just current vs. prior 30 days)
3. **Region-aware baselines** (20% growth in Mumbai ≠ 20% growth in rural Bihar)
4. **Real feedback loop** wired into a scheduled retraining job
5. **Smarter deduplication** (auto-resolve when only timestamps differ)

---

## 13. Demo Flow (What to Show)

### Happy Path (2 minutes)
1. Open `http://localhost:8000/interface`
2. Upload `sample_input.csv` (drag and drop)
3. Show the processing overlay animation
4. Walk through the results:
   - **Stats cards**: "27 partners processed, 6 escalated, 15/15 checks passed"
   - **Donut chart**: "Here's the breakdown — 11 Active, 5 Escalated, 2 each of Declining, Improving, Inactive, High-Potential, Risky"
   - **Verification panel**: "All 15 checks pass independently"
   - **Escalation table**: "These 6 partners were flagged — Partner 1021 has missing data, 1022 has broken totals, 1024 has KYC conflict..."
   - **Downloads**: "Manager gets 5 downloadable files"

### Failure Path (1 minute)
1. Upload a bad CSV with missing columns
2. Show the clear error: "Schema validation failed: Missing required columns..."
3. Explain: "No partial output — the system refuses to produce garbage"

### CLI Path (30 seconds)
```bash
python worker.py --input data/sample_input.csv --outdir output --logdir logs
python verify.py --input data/sample_input.csv --outdir output --logdir logs
# Shows: 15/15 checks passed
```

---

## 14. Key Talking Points to Emphasize

> These are the things that will impress evaluators:

1. **"I defined Definition of Done before writing code"** — shows systems thinking
2. **"21% of my data is intentionally dirty"** — shows you understand real-world data
3. **"The worker never guesses"** — shows you understand AI safety
4. **"I built a separate verifier that doesn't trust the worker"** — shows engineering rigor
5. **"Every decision has an audit trail"** — shows you understand compliance
6. **"KYC conflicts always escalate, even with great numbers"** — shows you understand Eko's business
7. **"Growth rate is undefined, not zero, for new partners"** — shows attention to correctness

---

## 15. One-Line Summary

> **"I built an AI Worker that takes messy partner data, validates it, classifies each partner's performance, escalates what it can't safely decide, and produces audit-ready reports — while handling 7 different types of failure correctly."**

# Data Dictionary & Assumptions

## Data dictionary — `data/sample_input.csv`

| Column | Type | Description |
|---|---|---|
| `partner_id` | int | Unique identifier for the partner/agent. |
| `partner_name` | string | Display name (synthetic in this sample). |
| `region` | string | Operating region/cluster. |
| `onboarding_date` | date (ISO) | Date the partner joined the network. |
| `kyc_status` | enum: Verified / Pending / Rejected | Current KYC compliance state. |
| `active_days_last_30` | int (0–30) | Number of days with ≥1 transaction in the last 30 days. |
| `txn_count_last_30` | int | Number of transactions in the last 30 days. |
| `txn_volume_gtv_last_30` | float (₹) | Gross transaction value in the last 30 days. |
| `txn_count_prev_30` | int | Transaction count in the prior 30-day window (for trend comparison). |
| `txn_volume_gtv_prev_30` | float (₹) | GTV in the prior 30-day window. |
| `complaints_last_30` | int | Customer/partner complaints logged in the last 30 days. |
| `service_uptime_pct` | float (0–100) | % of time the partner's service/device was available. |
| `declared_gtv_last_30` | float (₹) | GTV as declared/reported at period close. |
| `computed_gtv_last_30_from_daily_logs` | float (₹) | GTV independently summed from daily transaction logs — used to cross-check `declared_gtv_last_30`. |
| `last_txn_date` | date (ISO) or null | Date of the most recent transaction. |

## Assumptions

1. **30-day rolling windows** are the unit of analysis; the worker does not
   currently look further back than "current 30 days vs. prior 30 days."
2. **Declared vs. computed GTV** are assumed to come from two independent
   sources (e.g., a partner-reported summary vs. a system-computed daily
   ledger). A >2% mismatch is treated as a data-integrity problem worth a
   human look, not automatically "corrected" to either value.
3. **KYC status is authoritative** from whatever compliance system feeds it;
   the worker never overrides or infers KYC status — it only reacts to it.
4. **Growth rate is undefined, not zero**, when the prior-period volume is 0
   or missing (e.g., a brand-new partner). Treating undefined growth as 0%
   or infinite would misclassify legitimate new partners as "Declining" or
   "High-Potential" — a common silent bug this worker deliberately avoids.
5. **Exact duplicate rows** (same values across every column) are assumed to
   be a pipeline artifact (e.g., a file re-sent twice) and are safely
   deduplicated. **Same `partner_id` with different values** is assumed to be
   a genuine data conflict (e.g., two systems disagreeing) and is always
   escalated rather than guessed at.
6. Currency is assumed to be INR (₹), consistent with Eko's market, though
   the worker does not hardcode currency logic — it only compares numbers.
7. This is a **decision-support** worker, not a decision-execution system: it
   never writes back to a partner's account status, limits, or payouts. All
   "recommended actions" are advisory text for a human.

## Model / logic used

No ML model is used in this version — classification is done via explicit,
auditable business rules (see `src/worker.py:classify_partner`). This is an
intentional design choice for a first version: rule-based logic is fully
explainable to a compliance reviewer or field manager ("why was this partner
flagged Risky?" → "3 complaints in 30 days, see rule"), which matters more
than marginal accuracy gains at this stage. Section 13 of the README
describes the planned path to a model-assisted version once labeled
feedback data (manager agree/disagree) exists to train and validate against.

## Validation approach

Two layers, run in order:
1. **Schema validation** — required columns must be present, or the run
   aborts entirely rather than producing a partial/garbage output.
2. **Row-level semantic validation** — missing critical fields, negative
   values, out-of-range values, arithmetic mismatches (declared vs. computed
   GTV), KYC/activity conflicts, and duplicate IDs are each individually
   checked per row and logged with an `issue_type`, `detail`, and whether the
   issue is `blocking` (forces escalation) or advisory (`inconsistent_data`,
   logged but doesn't block classification).

Nothing is corrected automatically. The worker's job is to detect and route,
not to silently repair data it doesn't have the authority to fix.

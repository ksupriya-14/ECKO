# Failure & Exception Scenario Walkthrough

The assignment requires demonstrating what happens when something goes
wrong, not just a happy-path run. `data/sample_input.csv` intentionally
contains 6 broken/edge-case rows (out of 28 total). This document walks
through each one, what the worker did, and why that's the correct behavior.

Run the worker yourself to reproduce this exactly:
```bash
cd src && python3 worker.py --input ../data/sample_input.csv --outdir ../output --logdir ../logs
```

| # | Partner | Injected problem | Worker behavior | Why this is correct |
|---|---|---|---|---|
| 1 | `1021` Partner_MissingData | `txn_count_last_30`, `txn_volume_gtv_last_30`, `active_days_last_30` all blank | Flagged 3x `missing_field`, classification = `ESCALATE_DATA_ISSUE`, confidence 0.0, routed to `human_review_queue.csv` | Classifying with missing core fields would mean guessing. The worker refuses to guess and says exactly which fields are missing. |
| 2 | `1022` Partner_BrokenTotals | `declared_gtv_last_30`=500,000 vs `computed_gtv_last_30_from_daily_logs`=210,000 (58% mismatch) | Flagged `broken_total` with the exact percentage difference, escalated | A >2% mismatch between a partner's declared total and the independently computed total is a red flag for either a reporting error or something worse — a human needs to look at the underlying ledger, not have the worker silently pick one number. |
| 3 | `1023` Partner_NegativeVolume | `txn_volume_gtv_last_30` = -50,000 | Flagged `invalid_value`, escalated | Transaction volume can never be physically negative — this indicates a data pipeline bug (e.g., a refund miscoded as negative GTV instead of a separate field). Silently using `abs()` would mask the underlying bug. |
| 4 | `1024` Partner_KYCRejectedActive | `kyc_status`="Rejected" but 350 transactions in the last 30 days | Flagged `compliance_risk`, escalated regardless of otherwise-strong performance numbers | This is the highest-stakes case in the dataset: a partner with rejected KYC who is still actively transacting is a compliance/fraud concern. The worker treats this as an automatic, non-negotiable escalation — it never lets good transaction numbers override a compliance flag. |
| 5 | `1025` Partner_Dup (x2, identical rows) | Exact duplicate row (same partner_id, same everything) | Silently deduplicated (1 row dropped), logged as `drop_exact_duplicates` in both the validation report and audit log | Safe to auto-resolve — it's almost certainly a pipeline re-send, and the resolution (keep one) doesn't lose information. Still logged so it's auditable, not silent. |
| 6 | `1027` Partner_BadUptime | `service_uptime_pct` = 143.0 (impossible, must be 0–100) | Flagged `invalid_value` (out of range), escalated | An uptime percentage above 100% is physically impossible and signals a unit or calculation bug upstream (e.g., minutes counted as a percentage). |
| 7 | `1028` Partner_NewNoHistory | `txn_volume_gtv_prev_30` = 0 (new partner, no prior period) | Classified as `Active (New, insufficient history)` with an explicit reason, confidence 0.5 — below the 0.55 auto-approve threshold, so it's *also* routed to human review, but for a different reason (low confidence) than the hard data-quality escalations above | This is the "silent bug" case rather than a hard error: naive growth-rate code does `(curr - prev) / prev`, which would divide by zero or silently produce `inf`/`NaN` and likely misclassify a brand-new, perfectly healthy partner as "Declining" or crash the whole run. The worker special-cases the math so it never divides by zero, gives its best honest label, and lets the confidence gate (not a hard rule) decide whether a human should double check it. |

## What this demonstrates

- **6 of 28 rows (21%) were bad in different ways**, and the worker handled
  every type differently and correctly: two were unsafe to auto-resolve and
  were escalated with a specific reason (missing data, broken totals,
  negative values, compliance conflict, out-of-range value), one was safe to
  auto-resolve and was (with a log entry), and one was an edge case that
  needed special handling rather than either an escalation or a crash.
- **Nothing crashed and nothing was silently wrong.** A run with dirty data
  still produces a complete, trustworthy report — the bad rows are visible
  in `validation_report.md`, `human_review_queue.csv`, and `audit_log.csv`,
  not swallowed or hidden.
- **The reconciliation holds**: 28 input rows → 1 exact duplicate dropped →
  27 rows in the classification output, 6 escalated to human review (5 hard
  data-quality/compliance issues, plus the new-partner case escalated purely
  on low confidence, not a rule violation) — matching `summary_report.md`
  from the actual run.

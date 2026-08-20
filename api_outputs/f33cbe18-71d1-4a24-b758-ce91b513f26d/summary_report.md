# Micro-Entrepreneur Performance Worker — Run Summary

- Run started: 2026-08-20T14:42:09.724323+00:00
- Total partners processed: **27**
- Escalated to human review: **6** (22%)
- Duplicate rows dropped before processing: **1**

## Classification breakdown

| Classification | Count |
|---|---|
| Active | 11 |
| ESCALATE_DATA_ISSUE | 5 |
| Improving | 2 |
| Declining | 2 |
| Inactive | 2 |
| High-Potential | 2 |
| Risky | 2 |
| Active (New, insufficient history) | 1 |

## Items requiring human review

| Partner ID | Name | Flagged As | Reason |
|---|---|---|---|
| 1021 | Partner_MissingData | ESCALATE_DATA_ISSUE | missing_field: 'txn_count_last_30' is missing; missing_field: 'txn_volume_gtv_last_30' is missing; missing_field: 'active_days_last_30' is missing |
| 1022 | Partner_BrokenTotals | ESCALATE_DATA_ISSUE | broken_total: declared_gtv (500000.0) vs computed_gtv (210000.0) differ by 58.0%, exceeds 2% tolerance |
| 1023 | Partner_NegativeVolume | ESCALATE_DATA_ISSUE | invalid_value: 'txn_volume_gtv_last_30' is negative (-50000.0) |
| 1024 | Partner_KYCRejectedActive | ESCALATE_DATA_ISSUE | compliance_risk: KYC status is 'Rejected' but partner has 350.0 transactions in the last 30 days |
| 1027 | Partner_BadUptime | ESCALATE_DATA_ISSUE | invalid_value: service_uptime_pct out of range (143.0) |
| 1028 | Partner_NewNoHistory | Active (New, insufficient history) | No prior-period transaction volume available (new partner) — growth rate is undefined, not assumed zero. |

## How to confirm this run completed successfully

- `partner_classification_output.csv` contains exactly one row per unique, valid `partner_id` from the input (27 rows here).
- Every row has a non-null `classification`, `recommended_action`, and `confidence`.
- `human_review_queue.csv` lists every row where the worker declined to decide automatically, with a stated reason.
- `validation_report.md` accounts for every row dropped or flagged during ingestion.
- `audit_log.csv` (in /logs) has one or more entries for every partner_id, timestamped.

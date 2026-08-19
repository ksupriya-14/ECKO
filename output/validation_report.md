# Validation Report

- Exact duplicate rows dropped: **1**
- Rows with at least one data-quality issue: **5**

| Partner ID | Issue Type | Detail | Blocking? |
|---|---|---|---|
| 1021 | missing_field | 'txn_count_last_30' is missing | Yes |
| 1021 | missing_field | 'txn_volume_gtv_last_30' is missing | Yes |
| 1021 | missing_field | 'active_days_last_30' is missing | Yes |
| 1022 | broken_total | declared_gtv (500000.0) vs computed_gtv (210000.0) differ by 58.0%, exceeds 2% tolerance | Yes |
| 1023 | invalid_value | 'txn_volume_gtv_last_30' is negative (-50000.0) | Yes |
| 1024 | compliance_risk | KYC status is 'Rejected' but partner has 350.0 transactions in the last 30 days | Yes |
| 1027 | invalid_value | service_uptime_pct out of range (143.0) | Yes |

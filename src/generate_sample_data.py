"""
Generates a synthetic sample dataset of micro-entrepreneur (agent/retailer) partner activity.

The dataset intentionally includes several "dirty" rows so the AI Worker's
validation layer and escalation logic have real cases to catch. These are
documented in docs/data_dictionary_and_assumptions.md under "Intentional
failure rows".
"""
import pandas as pd
import numpy as np
import random

random.seed(42)
np.random.seed(42)

regions = ["Bihar-North", "Bihar-South", "UP-East", "UP-West", "Jharkhand", "MP-Central"]
kyc_states = ["Verified", "Pending", "Rejected"]

rows = []

def make_partner(pid, name, region, onboarding_days_ago, kyc, active_days, txn_count, txn_vol,
                  txn_count_prev, txn_vol_prev, complaints, uptime, declared_gtv, computed_gtv,
                  last_txn_days_ago):
    rows.append({
        "partner_id": pid,
        "partner_name": name,
        "region": region,
        "onboarding_date": (pd.Timestamp("2026-08-17") - pd.Timedelta(days=onboarding_days_ago)).date().isoformat(),
        "kyc_status": kyc,
        "active_days_last_30": active_days,
        "txn_count_last_30": txn_count,
        "txn_volume_gtv_last_30": txn_vol,
        "txn_count_prev_30": txn_count_prev,
        "txn_volume_gtv_prev_30": txn_vol_prev,
        "complaints_last_30": complaints,
        "service_uptime_pct": uptime,
        "declared_gtv_last_30": declared_gtv,
        "computed_gtv_last_30_from_daily_logs": computed_gtv,
        "last_txn_date": (pd.Timestamp("2026-08-17") - pd.Timedelta(days=last_txn_days_ago)).date().isoformat() if last_txn_days_ago is not None else None,
    })

# --- 25 normal, healthy-looking partners spanning different performance profiles ---
profiles = [
    # (active_days, txn_count, txn_vol, txn_count_prev, txn_vol_prev, complaints, uptime)
    (28, 410, 620000, 350, 500000, 0, 99.2),   # high-potential (growing fast)
    (26, 300, 450000, 260, 400000, 1, 97.0),   # improving
    (25, 280, 300000, 300, 310000, 0, 98.5),   # stable/active
    (22, 150, 180000, 220, 260000, 2, 95.0),   # declining
    (0, 0, 0, 180, 220000, 0, 90.0),           # inactive (went to zero)
    (27, 500, 900000, 300, 500000, 0, 99.5),   # high-potential
    (20, 120, 95000, 130, 100000, 0, 96.0),    # stable
    (24, 260, 210000, 200, 180000, 1, 97.5),   # improving
    (18, 90, 70000, 160, 150000, 3, 88.0),     # risky: high complaints
    (26, 310, 330000, 290, 300000, 0, 99.0),   # stable
]

pid = 1001
for i, p in enumerate(profiles * 2):  # 20 partners
    active_days, txn_count, txn_vol, txn_count_prev, txn_vol_prev, complaints, uptime = p
    declared = txn_vol
    computed = txn_vol  # totals match
    make_partner(
        pid, f"Partner_{pid}", random.choice(regions), random.randint(60, 900),
        "Verified" if complaints < 3 else "Verified",
        active_days, txn_count, txn_vol, txn_count_prev, txn_vol_prev,
        complaints, uptime, declared, computed,
        last_txn_days_ago=random.randint(0, 3) if active_days > 0 else random.randint(31, 90)
    )
    pid += 1

# --- INTENTIONAL FAILURE / EXCEPTION ROWS (for the required failure demo) ---

# 1. Missing critical fields (txn_count and txn_volume blank) -> insufficient data to classify
make_partner(pid, "Partner_MissingData", "UP-East", 200, "Verified",
             None, None, None, 280, 250000, 0, 96.0, None, None, None)
pid += 1

# 2. Broken totals: declared GTV does not match sum of daily logs (data integrity issue)
make_partner(pid, "Partner_BrokenTotals", "Jharkhand", 400, "Verified",
             24, 300, 500000, 280, 480000, 0, 97.0, declared_gtv=500000, computed_gtv=210000,
             last_txn_days_ago=1)
pid += 1

# 3. Invalid value: negative transaction volume (should never be negative)
make_partner(pid, "Partner_NegativeVolume", "MP-Central", 150, "Verified",
             20, 100, -50000, 90, 80000, 0, 95.0, declared_gtv=-50000, computed_gtv=-50000,
             last_txn_days_ago=2)
pid += 1

# 4. Compliance risk: KYC Rejected but still transacting heavily -> must escalate, not auto-decide
make_partner(pid, "Partner_KYCRejectedActive", "Bihar-North", 500, "Rejected",
             27, 350, 400000, 300, 350000, 1, 98.0, declared_gtv=400000, computed_gtv=400000,
             last_txn_days_ago=0)
pid += 1

# 5. Duplicate partner_id (data pipeline duplication issue)
make_partner(pid, "Partner_Dup", "Bihar-South", 300, "Verified",
             15, 80, 60000, 70, 55000, 0, 96.0, declared_gtv=60000, computed_gtv=60000,
             last_txn_days_ago=4)
dup_id = pid
pid += 1
make_partner(dup_id, "Partner_Dup", "Bihar-South", 300, "Verified",
             15, 80, 60000, 70, 55000, 0, 96.0, declared_gtv=60000, computed_gtv=60000,
             last_txn_days_ago=4)  # exact duplicate row

# 6. Out-of-range uptime (data entry error: >100%)
make_partner(pid + 1, "Partner_BadUptime", "UP-West", 250, "Verified",
             25, 200, 150000, 190, 145000, 0, 143.0, declared_gtv=150000, computed_gtv=150000,
             last_txn_days_ago=1)

# 7. Division-by-zero risk: prev period volume is zero (new-ish partner, growth undefined)
make_partner(pid + 2, "Partner_NewNoHistory", "Bihar-North", 20, "Verified",
             18, 60, 45000, 0, 0, 0, 97.0, declared_gtv=45000, computed_gtv=45000,
             last_txn_days_ago=1)

df = pd.DataFrame(rows)
output_path = "../data/sample_input.csv"
df.to_csv(output_path, index=False)
print(f"Generated {len(df)} rows -> {output_path}")
print(df.tail(9)[["partner_id","partner_name","kyc_status","txn_count_last_30","declared_gtv_last_30","computed_gtv_last_30_from_daily_logs"]])

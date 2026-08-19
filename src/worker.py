"""
Micro-Entrepreneur Performance Worker
======================================
An AI Worker that ingests partner (agent/retailer) activity data and:
  1. Validates the data (structure, completeness, ranges, arithmetic consistency).
  2. Classifies each partner into one of: Active, Inactive, Improving,
     Declining, Risky, High-Potential.
  3. Recommends a next action per partner.
  4. Produces a per-partner output report + a manager-facing summary report.
  5. Logs every decision to an audit trail.
  6. Routes anything it cannot safely decide to a Human Review Queue instead
     of guessing.

Run:  python3 worker.py --input ../data/sample_input.csv --outdir ../output --logdir ../logs
"""
import argparse
import json
import sys
from datetime import datetime, timezone


class WorkerError(Exception):
    """Raised when the worker encounters a fatal validation or data error."""
    pass

import numpy as np
import pandas as pd

REQUIRED_COLUMNS = [
    "partner_id", "partner_name", "region", "onboarding_date", "kyc_status",
    "active_days_last_30", "txn_count_last_30", "txn_volume_gtv_last_30",
    "txn_count_prev_30", "txn_volume_gtv_prev_30", "complaints_last_30",
    "service_uptime_pct", "declared_gtv_last_30",
    "computed_gtv_last_30_from_daily_logs", "last_txn_date",
]

CRITICAL_FOR_CLASSIFICATION = [
    "txn_count_last_30", "txn_volume_gtv_last_30", "active_days_last_30",
]

GTV_TOLERANCE_PCT = 0.02  # declared vs computed GTV may differ by at most 2%
CONFIDENCE_ESCALATION_THRESHOLD = 0.55  # below this, send to human review


def now_iso():
    return datetime.now(timezone.utc).isoformat()


class AuditLogger:
    """Append-only audit trail of every decision the worker makes."""

    def __init__(self):
        self.records = []

    def log(self, partner_id, stage, decision, reason, severity="info"):
        self.records.append({
            "timestamp": now_iso(),
            "partner_id": partner_id,
            "stage": stage,          # validation | classification | escalation
            "decision": decision,
            "reason": reason,
            "severity": severity,    # info | warning | error
        })

    def to_dataframe(self):
        return pd.DataFrame(self.records)


class ValidationResult:
    def __init__(self):
        self.row_issues = {}   # partner_id (or row index) -> list of issue dicts
        self.dropped_duplicate_rows = 0
        self.schema_errors = []

    def add_issue(self, key, issue_type, detail, blocking):
        self.row_issues.setdefault(key, []).append(
            {"issue_type": issue_type, "detail": detail, "blocking": blocking}
        )


def validate(df: pd.DataFrame, audit: AuditLogger) -> tuple[pd.DataFrame, ValidationResult]:
    """
    Structural + semantic validation.
    - Checks schema (required columns present).
    - Flags missing critical fields, out-of-range values, negative volumes,
      arithmetic mismatches (declared vs computed GTV), and duplicate rows.
    - Nothing is silently dropped except exact duplicate rows (logged).
    Returns the (deduplicated) dataframe plus a ValidationResult describing
    every issue found, keyed by partner_id, so classify() can decide what to
    do with each row (classify normally / classify with caveat / escalate).
    """
    result = ValidationResult()

    missing_cols = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing_cols:
        result.schema_errors.append(f"Missing required columns: {missing_cols}")
        audit.log("SCHEMA", "validation", "reject_file",
                   f"Missing required columns: {missing_cols}", "error")
        return df, result

    # Exact duplicate rows (same partner_id + identical data) -> drop, log, keep one
    before = len(df)
    df = df.drop_duplicates()
    result.dropped_duplicate_rows = before - len(df)
    if result.dropped_duplicate_rows:
        audit.log("MULTIPLE", "validation", "drop_exact_duplicates",
                   f"Dropped {result.dropped_duplicate_rows} exact duplicate row(s)", "warning")

    # Duplicate partner_id with differing data -> cannot silently pick one; escalate both
    dup_id_mask = df["partner_id"].duplicated(keep=False)
    for pid in df.loc[dup_id_mask, "partner_id"].unique():
        result.add_issue(pid, "duplicate_partner_id",
                          f"partner_id {pid} appears in {dup_id_mask.sum()} non-identical rows",
                          blocking=True)
        audit.log(pid, "validation", "flag_duplicate_id",
                   "Same partner_id with conflicting data", "error")

    for _, row in df.iterrows():
        pid = row["partner_id"]

        # Type validation: ensure numeric fields are actually numeric
        numeric_cols = ["txn_count_last_30", "txn_volume_gtv_last_30", "active_days_last_30",
                        "txn_count_prev_30", "txn_volume_gtv_prev_30", "complaints_last_30",
                        "service_uptime_pct", "declared_gtv_last_30", "computed_gtv_last_30_from_daily_logs"]
        for col in numeric_cols:
            val = row.get(col)
            if pd.notna(val):
                try:
                    # Attempt to convert to float to catch string values
                    float(val)
                except (ValueError, TypeError):
                    result.add_issue(pid, "invalid_value", f"'{col}' has non-numeric value: {val}", blocking=True)
                    audit.log(pid, "validation", "flag_non_numeric", f"'{col}'={val}", "error")

        # Missing critical fields
        for col in CRITICAL_FOR_CLASSIFICATION:
            if pd.isna(row[col]):
                result.add_issue(pid, "missing_field", f"'{col}' is missing", blocking=True)
                audit.log(pid, "validation", "flag_missing_field", f"'{col}' is missing", "error")

        # Negative values that should never be negative
        for col in ["txn_count_last_30", "txn_volume_gtv_last_30", "active_days_last_30",
                    "complaints_last_30"]:
            val = row.get(col)
            if pd.notna(val):
                try:
                    val_float = float(val)
                    if val_float < 0:
                        result.add_issue(pid, "invalid_value", f"'{col}' is negative ({val})", blocking=True)
                        audit.log(pid, "validation", "flag_negative_value", f"'{col}'={val}", "error")
                except (ValueError, TypeError):
                    # Already flagged as non-numeric above
                    pass

        # Out-of-range uptime (0-100%)
        uptime = row.get("service_uptime_pct")
        if pd.notna(uptime):
            try:
                uptime_float = float(uptime)
                if not (0 <= uptime_float <= 100):
                    result.add_issue(pid, "invalid_value", f"service_uptime_pct out of range ({uptime})",
                                      blocking=True)
                    audit.log(pid, "validation", "flag_out_of_range", f"service_uptime_pct={uptime}", "error")
            except (ValueError, TypeError):
                # Already flagged as non-numeric above
                pass

        # Arithmetic consistency: declared GTV vs sum of daily logs
        declared = row.get("declared_gtv_last_30")
        computed = row.get("computed_gtv_last_30_from_daily_logs")
        if pd.notna(declared) and pd.notna(computed):
            try:
                declared_float = float(declared)
                computed_float = float(computed)
                denom = max(abs(declared_float), 1)
                diff_pct = abs(declared_float - computed_float) / denom
                if diff_pct > GTV_TOLERANCE_PCT:
                    result.add_issue(
                        pid, "broken_total",
                        f"declared_gtv ({declared}) vs computed_gtv ({computed}) differ by "
                        f"{diff_pct:.1%}, exceeds {GTV_TOLERANCE_PCT:.0%} tolerance",
                        blocking=True,
                    )
                    audit.log(pid, "validation", "flag_broken_total",
                               f"declared={declared} computed={computed} diff={diff_pct:.1%}", "error")
            except (ValueError, TypeError):
                # Already flagged as non-numeric above
                pass

        # Compliance flag: KYC not verified but actively transacting
        if row.get("kyc_status") != "Verified" and pd.notna(row.get("txn_count_last_30")) \
                and row.get("txn_count_last_30", 0) > 0:
            result.add_issue(
                pid, "compliance_risk",
                f"KYC status is '{row.get('kyc_status')}' but partner has "
                f"{row.get('txn_count_last_30')} transactions in the last 30 days",
                blocking=True,
            )
            audit.log(pid, "validation", "flag_compliance_risk",
                       f"kyc_status={row.get('kyc_status')}", "error")

        # Staleness: no valid last_txn_date but claims active days > 0
        if pd.isna(row.get("last_txn_date")) and pd.notna(row.get("active_days_last_30")) \
                and row.get("active_days_last_30", 0) > 0:
            result.add_issue(pid, "inconsistent_data",
                              "active_days_last_30 > 0 but last_txn_date is missing",
                              blocking=False)
            audit.log(pid, "validation", "flag_inconsistent_data",
                       "active_days>0 but no last_txn_date", "warning")

    return df, result


def compute_growth_rate(curr, prev):
    """Safe growth rate. Returns None if undefined (no prior-period baseline)."""
    if prev in (0, None) or pd.isna(prev):
        return None
    if pd.isna(curr):
        return None
    return (curr - prev) / prev


def classify_partner(row, issues, audit: AuditLogger):
    """
    Returns a dict describing the classification decision for one partner,
    OR an escalation record if the worker cannot safely decide.

    Priority order (highest first):
      1. Blocking data-quality issue -> ESCALATE (never guess on bad data)
      2. Compliance risk (KYC not verified + active) -> ESCALATE
      3. Inactive (zero activity)
      4. Risky (complaints / uptime breach), even if numbers look fine
      5. Growth-rate based: High-Potential / Improving / Declining / Active
    """
    pid = row["partner_id"]
    blocking = [i for i in issues if i.get("blocking")]

    if blocking:
        reasons = "; ".join(f"{i['issue_type']}: {i['detail']}" for i in blocking)
        audit.log(pid, "classification", "escalate",
                   f"Blocking data issue(s) prevent classification: {reasons}", "error")
        return {
            "partner_id": pid, "partner_name": row.get("partner_name"),
            "classification": "ESCALATE_DATA_ISSUE",
            "recommended_action": "Route to Data/Ops team for correction before any performance decision is made.",
            "confidence": 0.0,
            "reasoning": reasons,
            "escalate": True,
        }

    complaints = row.get("complaints_last_30", 0) or 0
    uptime = row.get("service_uptime_pct", 100) or 100
    active_days = row.get("active_days_last_30", 0) or 0
    txn_count = row.get("txn_count_last_30", 0) or 0
    txn_vol = row.get("txn_volume_gtv_last_30", 0) or 0
    prev_vol = row.get("txn_volume_gtv_prev_30")

    growth = compute_growth_rate(txn_vol, prev_vol)

    # Inactive
    if active_days == 0 or txn_count == 0:
        audit.log(pid, "classification", "classify", "Inactive: zero activity in last 30 days", "info")
        return {
            "partner_id": pid, "partner_name": row.get("partner_name"),
            "classification": "Inactive",
            "recommended_action": "Trigger reactivation outreach call; check for device/service blockers.",
            "confidence": 0.9,
            "reasoning": "Zero active days or zero transactions in the last 30 days.",
            "escalate": False,
        }

    # Risky (quality/compliance signal, independent of volume trend)
    if complaints >= 3 or uptime < 80:
        audit.log(pid, "classification", "classify",
                   f"Risky: complaints={complaints}, uptime={uptime}", "info")
        return {
            "partner_id": pid, "partner_name": row.get("partner_name"),
            "classification": "Risky",
            "recommended_action": "Escalate to field quality team; review complaint tickets and device uptime before further incentive payout.",
            "confidence": 0.8,
            "reasoning": f"{complaints} complaint(s) in 30 days and/or service uptime {uptime}% below 80% threshold.",
            "escalate": complaints >= 5,  # extreme complaint volume -> human review, not just a tag
        }

    # Growth undefined (new partner, no prior baseline) -> cannot classify Improving/Declining
    if growth is None:
        audit.log(pid, "classification", "classify",
                   "New partner, no prior-period baseline for growth comparison", "info")
        return {
            "partner_id": pid, "partner_name": row.get("partner_name"),
            "classification": "Active (New, insufficient history)",
            "recommended_action": "Continue standard onboarding support; revisit trend classification after next cycle once a prior-period baseline exists.",
            "confidence": 0.5,
            "reasoning": "No prior-period transaction volume available (new partner) — growth rate is undefined, not assumed zero.",
            "escalate": False,
        }

    if growth >= 0.5 and txn_count >= 200 and active_days >= 20:
        cls, action, reason = ("High-Potential",
            "Fast-track for higher transaction limits / incentive tier upgrade; assign relationship manager for growth support.",
            f"GTV grew {growth:.0%} month-over-month with strong activity ({txn_count} txns, {active_days} active days).")
        conf = 0.85
    elif growth >= 0.2:
        cls, action, reason = ("Improving",
            "Monitor positively; offer targeted cross-sell (new products) to sustain momentum.",
            f"GTV grew {growth:.0%} month-over-month.")
        conf = 0.75
    elif growth <= -0.2:
        cls, action, reason = ("Declining",
            "Proactive retention call within 7 days; investigate cause (competitor, service issue, liquidity).",
            f"GTV declined {growth:.0%} month-over-month.")
        conf = 0.75
    else:
        cls, action, reason = ("Active",
            "No action needed; continue standard monitoring cadence.",
            f"GTV change of {growth:.0%} is within normal stable range.")
        conf = 0.7

    audit.log(pid, "classification", "classify", reason, "info")
    return {
        "partner_id": pid, "partner_name": row.get("partner_name"),
        "classification": cls, "recommended_action": action,
        "confidence": conf, "reasoning": reason, "escalate": False,
    }


def run_worker(input_path, outdir, logdir):
    audit = AuditLogger()
    run_started = now_iso()

    try:
        df = pd.read_csv(input_path)
    except Exception as e:
        # Cannot even open the file -> hard escalation, nothing else runs
        audit.log("FILE", "ingest", "abort", f"Could not read input file: {e}", "error")
        _write_audit(audit, logdir)
        msg = f"Could not read input file: {e}"
        print(f"FATAL: {msg}. Run aborted and logged.", file=sys.stderr)
        raise WorkerError(msg)

    # Check for empty dataset
    if len(df) == 0:
        audit.log("FILE", "ingest", "abort", "Input file is empty (no rows to process)", "error")
        _write_audit(audit, logdir)
        msg = "Input file is empty (no rows to process)"
        print(f"FATAL: {msg}. Run aborted and logged.", file=sys.stderr)
        raise WorkerError(msg)

    audit.log("FILE", "ingest", "load", f"Loaded {len(df)} rows from {input_path}", "info")

    df, val_result = validate(df, audit)

    if val_result.schema_errors:
        _write_audit(audit, logdir)
        msg = f"Schema validation failed: {val_result.schema_errors}"
        print(f"FATAL: {msg}", file=sys.stderr)
        raise WorkerError(msg)

    results = []
    for _, row in df.iterrows():
        pid = row["partner_id"]
        issues = val_result.row_issues.get(pid, [])
        decision = classify_partner(row, issues, audit)
        decision["data_issues_found"] = "; ".join(
            f"{i['issue_type']}: {i['detail']}" for i in issues
        ) if issues else ""
        results.append(decision)

    out_df = pd.DataFrame(results)

    # Confidence-based escalation on top of rule-based escalation
    low_conf_mask = (out_df["confidence"] < CONFIDENCE_ESCALATION_THRESHOLD) & (~out_df["escalate"])
    out_df.loc[low_conf_mask, "escalate"] = True
    for pid in out_df.loc[low_conf_mask, "partner_id"]:
        audit.log(pid, "escalation", "escalate_low_confidence",
                   f"Confidence below {CONFIDENCE_ESCALATION_THRESHOLD} threshold", "warning")

    out_path = f"{outdir}/partner_classification_output.csv"
    out_df.to_csv(out_path, index=False)

    escalations = out_df[out_df["escalate"]]
    esc_path = f"{outdir}/human_review_queue.csv"
    escalations.to_csv(esc_path, index=False)

    summary = _build_summary(out_df, val_result, run_started)
    summary_path = f"{outdir}/summary_report.md"
    with open(summary_path, "w") as f:
        f.write(summary)

    validation_report = _build_validation_report(val_result)
    val_path = f"{outdir}/validation_report.md"
    with open(val_path, "w") as f:
        f.write(validation_report)

    audit_path = _write_audit(audit, logdir)

    print(f"Done.\n  Classified output : {out_path}\n  Human review queue: {esc_path}\n"
          f"  Summary report     : {summary_path}\n  Validation report  : {val_path}\n"
          f"  Audit log          : {audit_path}")

    return out_df, val_result, audit


def _write_audit(audit, logdir):
    path = f"{logdir}/audit_log.csv"
    audit.to_dataframe().to_csv(path, index=False)
    return path


def _build_validation_report(val_result: ValidationResult) -> str:
    lines = ["# Validation Report\n"]
    lines.append(f"- Exact duplicate rows dropped: **{val_result.dropped_duplicate_rows}**")
    total_flagged = len(val_result.row_issues)
    lines.append(f"- Rows with at least one data-quality issue: **{total_flagged}**\n")

    if not val_result.row_issues:
        lines.append("No data quality issues found.\n")
        return "\n".join(lines)

    lines.append("| Partner ID | Issue Type | Detail | Blocking? |")
    lines.append("|---|---|---|---|")
    for pid, issues in val_result.row_issues.items():
        for i in issues:
            lines.append(f"| {pid} | {i['issue_type']} | {i['detail']} | "
                          f"{'Yes' if i['blocking'] else 'No'} |")
    return "\n".join(lines) + "\n"


def _build_summary(out_df, val_result, run_started):
    counts = out_df["classification"].value_counts().to_dict()
    n_escalated = int(out_df["escalate"].sum())
    n_total = len(out_df)

    lines = [
        "# Micro-Entrepreneur Performance Worker — Run Summary\n",
        f"- Run started: {run_started}",
        f"- Total partners processed: **{n_total}**",
        f"- Escalated to human review: **{n_escalated}** ({n_escalated/n_total:.0%})",
        f"- Duplicate rows dropped before processing: **{val_result.dropped_duplicate_rows}**\n",
        "## Classification breakdown\n",
        "| Classification | Count |",
        "|---|---|",
    ]
    for cls, count in sorted(counts.items(), key=lambda x: -x[1]):
        lines.append(f"| {cls} | {count} |")

    lines.append("\n## Items requiring human review\n")
    esc = out_df[out_df["escalate"]][["partner_id", "partner_name", "classification", "reasoning"]]
    if esc.empty:
        lines.append("None — all partners classified with sufficient confidence and clean data.\n")
    else:
        lines.append("| Partner ID | Name | Flagged As | Reason |")
        lines.append("|---|---|---|---|")
        for _, r in esc.iterrows():
            lines.append(f"| {r.partner_id} | {r.partner_name} | {r.classification} | {r.reasoning} |")

    lines.append("\n## How to confirm this run completed successfully\n")
    lines.append(
        "- `partner_classification_output.csv` contains exactly one row per unique, valid "
        f"`partner_id` from the input ({n_total} rows here).\n"
        "- Every row has a non-null `classification`, `recommended_action`, and `confidence`.\n"
        "- `human_review_queue.csv` lists every row where the worker declined to decide "
        "automatically, with a stated reason.\n"
        "- `validation_report.md` accounts for every row dropped or flagged during ingestion.\n"
        "- `audit_log.csv` (in /logs) has one or more entries for every partner_id, timestamped.\n"
    )
    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="../data/sample_input.csv")
    parser.add_argument("--outdir", default="../output")
    parser.add_argument("--logdir", default="../logs")
    args = parser.parse_args()
    run_worker(args.input, args.outdir, args.logdir)

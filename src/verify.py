"""
Verification harness for the Micro-Entrepreneur Performance Worker.

This does NOT re-implement the worker's logic. It independently checks the
worker's *outputs* against the Definition of Done in README.md — the same
way a QA reviewer would, without trusting the worker's own claims about
itself.

Run:  python3 verify.py --outdir ../output --logdir ../logs --input ../data/sample_input.csv
Exit code 0 = all checks passed. Non-zero = at least one failed (see printed report).
"""
import argparse
import sys
import pandas as pd


class Check:
    def __init__(self, name):
        self.name = name
        self.passed = None
        self.detail = ""

    def ok(self, detail=""):
        self.passed = True
        self.detail = detail
        return self

    def fail(self, detail=""):
        self.passed = False
        self.detail = detail
        return self


def verify(input_path, outdir, logdir):
    checks = []

    raw = pd.read_csv(input_path)
    out = pd.read_csv(f"{outdir}/partner_classification_output.csv")
    val_report = open(f"{outdir}/validation_report.md").read()
    summary = open(f"{outdir}/summary_report.md").read()
    review_q = pd.read_csv(f"{outdir}/human_review_queue.csv")
    audit = pd.read_csv(f"{logdir}/audit_log.csv")

    # --- Row reconciliation ---
    c = Check("Row reconciliation: input rows = output rows + exact duplicates dropped")
    dup_dropped = len(raw) - len(raw.drop_duplicates())
    unique_input_ids = raw.drop_duplicates()["partner_id"].nunique()
    if len(out) == unique_input_ids:
        c.ok(f"input={len(raw)} rows, exact dupes dropped={dup_dropped}, "
             f"unique ids after dedup={unique_input_ids}, output rows={len(out)}")
    else:
        c.fail(f"MISMATCH: unique ids after dedup={unique_input_ids} but output has {len(out)} rows")
    checks.append(c)

    # --- No nulls in required output columns ---
    for col in ["classification", "recommended_action", "confidence"]:
        c = Check(f"No missing values in output column '{col}'")
        n_null = out[col].isna().sum()
        c.ok() if n_null == 0 else c.fail(f"{n_null} null value(s) found")
        checks.append(c)

    # --- Every escalated row has a non-empty reason ---
    c = Check("Every escalated row has a stated reason")
    empty_reason = review_q[review_q["reasoning"].isna() | (review_q["reasoning"] == "")]
    c.ok(f"{len(review_q)} escalated rows, all have reasons") if empty_reason.empty \
        else c.fail(f"{len(empty_reason)} escalated row(s) missing a reason")
    checks.append(c)

    # --- Confidence gate actually enforced ---
    c = Check("Every row with confidence < 0.55 is flagged for escalation")
    low_conf_not_escalated = out[(out["confidence"] < 0.55) & (~out["escalate"])]
    c.ok() if low_conf_not_escalated.empty else c.fail(
        f"{len(low_conf_not_escalated)} row(s) below confidence threshold but NOT escalated: "
        f"{low_conf_not_escalated['partner_id'].tolist()}")
    checks.append(c)

    # --- Known injected failure cases were actually caught ---
    expected_escalations = {
        1021: "missing data",
        1022: "broken totals",
        1023: "negative value",
        1024: "KYC/compliance conflict",
    }
    for pid, label in expected_escalations.items():
        c = Check(f"Injected case {pid} ({label}) was escalated")
        row = out[out["partner_id"] == pid]
        if row.empty:
            c.fail(f"partner_id {pid} not found in output at all")
        elif bool(row.iloc[0]["escalate"]):
            c.ok()
        else:
            c.fail(f"partner_id {pid} present but NOT escalated (classification="
                   f"{row.iloc[0]['classification']})")
        checks.append(c)

    # --- No compliance override: a KYC-conflict row must never be labeled a positive class ---
    c = Check("KYC-conflict partner (1024) was never given a normal performance label")
    row = out[out["partner_id"] == 1024]
    bad_labels = {"Active", "Improving", "High-Potential"}
    if not row.empty and row.iloc[0]["classification"] not in bad_labels:
        c.ok(f"classification = {row.iloc[0]['classification']}")
    else:
        c.fail("Compliance conflict was overridden by a normal performance label — CRITICAL BUG")
    checks.append(c)

    # --- Audit log covers every partner processed ---
    c = Check("Audit log has at least one entry per partner_id in the output")
    missing_from_audit = set(out["partner_id"]) - set(audit["partner_id"].astype(str).str.extract(r"(\d+)")[0].dropna().astype(float).astype(int))
    # fallback simpler check: partner_id present as-is (audit stores as string/number mixed with 'FILE'/'MULTIPLE')
    audit_ids = set(pd.to_numeric(audit["partner_id"], errors="coerce").dropna().astype(int))
    missing_from_audit = set(out["partner_id"]) - audit_ids
    c.ok(f"{len(audit)} audit entries, {len(audit_ids)} unique partner ids logged") if not missing_from_audit \
        else c.fail(f"{len(missing_from_audit)} partner(s) never appear in the audit log: {missing_from_audit}")
    checks.append(c)

    # --- Reports are non-trivial (not empty placeholders) ---
    for name, content in [("validation_report.md", val_report), ("summary_report.md", summary)]:
        c = Check(f"{name} is non-empty and substantive")
        c.ok(f"{len(content)} chars") if len(content) > 200 else c.fail(f"only {len(content)} chars — looks empty/stub")
        checks.append(c)

    # --- No classification silently invented outside the known label set ---
    valid_labels = {"Active", "Inactive", "Improving", "Declining", "Risky", "High-Potential",
                     "ESCALATE_DATA_ISSUE", "Active (New, insufficient history)"}
    c = Check("All classifications are within the defined label set")
    unknown = set(out["classification"]) - valid_labels
    c.ok() if not unknown else c.fail(f"Unexpected label(s) produced: {unknown}")
    checks.append(c)

    return checks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="../data/sample_input.csv")
    parser.add_argument("--outdir", default="../output")
    parser.add_argument("--logdir", default="../logs")
    args = parser.parse_args()

    checks = verify(args.input, args.outdir, args.logdir)

    print("=" * 70)
    print("VERIFICATION REPORT — Micro-Entrepreneur Performance Worker")
    print("=" * 70)
    n_pass = sum(1 for c in checks if c.passed)
    for c in checks:
        status = "PASS" if c.passed else "FAIL"
        print(f"[{status}] {c.name}")
        if c.detail:
            print(f"       {c.detail}")
    print("=" * 70)
    print(f"{n_pass}/{len(checks)} checks passed")

    if n_pass != len(checks):
        sys.exit(1)


if __name__ == "__main__":
    main()

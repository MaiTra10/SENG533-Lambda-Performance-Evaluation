#!/usr/bin/env python3

"""
Summarize Experiment 3 enriched CSVs.

Outputs:
  data/experiment3/summary_exp3.csv

Summarizes by:
  - function
  - runtime
  - phase: cold/warm

Metrics:
  - total requests
  - successful requests
  - error rate
  - timeout rate
  - throughput
  - end-to-end latency stats
  - execution duration stats
  - init duration stats
"""

import argparse
from pathlib import Path

import pandas as pd


def safe_mean(series):
    series = pd.to_numeric(series, errors="coerce").dropna()

    if series.empty:
        return ""

    return series.mean()


def safe_median(series):
    series = pd.to_numeric(series, errors="coerce").dropna()

    if series.empty:
        return ""

    return series.median()


def safe_quantile(series, q):
    series = pd.to_numeric(series, errors="coerce").dropna()

    if series.empty:
        return ""

    return series.quantile(q)


def safe_max(series):
    series = pd.to_numeric(series, errors="coerce").dropna()

    if series.empty:
        return ""

    return series.max()


def calculate_throughput(successful_df):
    if len(successful_df) < 2:
        return ""

    start = successful_df["timestamp_sent"].min()
    end = successful_df["timestamp_sent"].max()

    duration = end - start

    if duration <= 0:
        return ""

    return len(successful_df) / duration


def summarize_file(csv_path):
    df = pd.read_csv(csv_path)

    function_name = csv_path.name.replace("results_", "").replace("_exp3.csv", "")

    rows = []

    for phase in ["cold", "warm"]:
        phase_df = df[df["phase"] == phase].copy()

        if phase_df.empty:
            continue

        phase_df["error"] = phase_df["error"].fillna("")
        phase_df["is_timeout"] = phase_df["is_timeout"].astype(str).str.lower()

        successful_df = phase_df[
            (phase_df["http_status"] == 200)
            & (phase_df["error"] == "")
        ]

        total = len(phase_df)
        successful = len(successful_df)
        errors = total - successful
        timeouts = phase_df["is_timeout"].eq("true").sum()

        runtime = ""

        if "runtime" in phase_df.columns and not phase_df["runtime"].dropna().empty:
            runtime = phase_df["runtime"].dropna().iloc[0]

        row = {
            "function": function_name,
            "runtime": runtime,
            "phase": phase,

            "total_requests": total,
            "successful_requests": successful,
            "errors": errors,
            "timeouts": timeouts,

            "error_rate_percent": (errors / total) * 100 if total else "",
            "timeout_rate_percent": (timeouts / total) * 100 if total else "",

            "throughput_req_per_sec": calculate_throughput(successful_df),

            "latency_mean_ms": safe_mean(successful_df["latency_ms"]),
            "latency_median_ms": safe_median(successful_df["latency_ms"]),
            "latency_p95_ms": safe_quantile(successful_df["latency_ms"], 0.95),
            "latency_p99_ms": safe_quantile(successful_df["latency_ms"], 0.99),
            "latency_max_ms": safe_max(successful_df["latency_ms"]),

            "execution_mean_ms": safe_mean(successful_df["execution_ms"]) if "execution_ms" in successful_df.columns else "",
            "execution_median_ms": safe_median(successful_df["execution_ms"]) if "execution_ms" in successful_df.columns else "",
            "execution_p95_ms": safe_quantile(successful_df["execution_ms"], 0.95) if "execution_ms" in successful_df.columns else "",

            "init_duration_mean_ms": safe_mean(successful_df["init_duration_ms"]) if "init_duration_ms" in successful_df.columns else "",
            "init_duration_median_ms": safe_median(successful_df["init_duration_ms"]) if "init_duration_ms" in successful_df.columns else "",
            "init_duration_max_ms": safe_max(successful_df["init_duration_ms"]) if "init_duration_ms" in successful_df.columns else "",
        }

        rows.append(row)

    return rows


def main():
    parser = argparse.ArgumentParser(
        description="Summarize Experiment 3 cold vs warm results."
    )

    parser.add_argument(
        "--dir",
        default="data/experiment3",
        help="Directory containing enriched Experiment 3 CSVs",
    )

    parser.add_argument(
        "--output",
        default="data/experiment3/summary_exp3.csv",
        help="Output summary CSV path",
    )

    args = parser.parse_args()

    data_dir = Path(args.dir)
    output_path = Path(args.output)

    all_rows = []

    for csv_path in sorted(data_dir.glob("results_*_exp3.csv")):
        all_rows.extend(summarize_file(csv_path))

    summary = pd.DataFrame(all_rows)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(output_path, index=False)

    print(summary.to_string(index=False))
    print()
    print(f"Saved summary to: {output_path}")


if __name__ == "__main__":
    main()
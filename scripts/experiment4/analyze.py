#!/usr/bin/env python3
"""
Experiment 4 — Burst vs Sustained analysis.

Reads CSV files produced by load_test.py from data/experiment4/ and generates
comparison plots for: end-to-end latency, throughput, error rate, timeout rate.
Execution duration is pulled from CloudWatch Logs Insights.

Usage:
    python3 scripts/experiment4/analyze.py \
        --sustained data/experiment4/results_exp4-python-x86-sustained_<ts>.csv \
        --burst     data/experiment4/results_exp4-python-x86-burst_<ts>.csv \
        --output-dir plots/experiment4

    # Also pull execution duration from CloudWatch:
    python3 scripts/experiment4/analyze.py \
        --sustained data/experiment4/results_..._sustained.csv \
        --burst     data/experiment4/results_..._burst.csv \
        --function  exp4-python-x86 \
        --region    us-west-2 \
        --start     1h \
        --output-dir plots/experiment4
"""

import argparse
import csv
import glob
import statistics
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


# ── CSV helpers ───────────────────────────────────────────────────────────────

def load_csv(path: str) -> list[dict]:
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def measurement_rows(rows: list[dict]) -> list[dict]:
    # sustained uses phase="measurement"; burst uses phase="spike"
    filtered = [r for r in rows if r.get("phase") in ("measurement", "spike")]
    return filtered if filtered else rows


# ── Metric extraction ─────────────────────────────────────────────────────────

def latencies(rows):
    return [float(r["latency_ms"]) for r in rows if r["error"] == "" and r["http_status"] == "200"]


def error_rate(rows) -> float:
    if not rows:
        return 0.0
    errors = sum(1 for r in rows if r["http_status"] != "200" or r["error"] != "")
    return errors / len(rows) * 100


def timeout_rate(rows) -> float:
    if not rows:
        return 0.0
    timeouts = sum(1 for r in rows if "TimeoutError" in r["error"] or r["http_status"] == "0")
    return timeouts / len(rows) * 100


def throughput_series(rows, bucket_secs=5):
    """Return (time_offsets, req_per_sec) bucketed over time."""
    if not rows:
        return [], []
    t0 = min(float(r["timestamp_sent"]) for r in rows)
    buckets: dict[int, int] = {}
    for r in rows:
        bucket = int((float(r["timestamp_sent"]) - t0) / bucket_secs)
        buckets[bucket] = buckets.get(bucket, 0) + 1
    max_bucket = max(buckets)
    offsets = [b * bucket_secs for b in range(max_bucket + 1)]
    counts  = [buckets.get(b, 0) / bucket_secs for b in range(max_bucket + 1)]
    return offsets, counts


# ── CloudWatch execution duration ─────────────────────────────────────────────

def query_cloudwatch(function_name, start_time, end_time, region):
    try:
        import boto3
    except ImportError:
        print("boto3 not installed — skipping CloudWatch execution duration.")
        return None, None

    client    = boto3.client("logs", region_name=region)
    log_group = f"/aws/lambda/{function_name}"
    query = (
        "filter @type = \"REPORT\"\n"
        "| fields @duration\n"
        "| sort @timestamp asc\n"
        "| limit 10000"
    )
    response = client.start_query(
        logGroupName=log_group,
        startTime=int(start_time.timestamp()),
        endTime=int(end_time.timestamp()),
        queryString=query,
    )
    qid = response["queryId"]
    while True:
        result = client.get_query_results(queryId=qid)
        if result["status"] == "Complete":
            break
        if result["status"] == "Failed":
            print(f"CloudWatch query failed for {function_name}")
            return None, None
        time.sleep(1)

    durations = []
    for row in result["results"]:
        for field in row:
            if field["field"] == "@duration":
                try:
                    durations.append(float(field["value"]))
                except ValueError:
                    pass
    return durations


# ── Plots ─────────────────────────────────────────────────────────────────────

COLORS = {"sustained": "#3776AB", "burst": "#E84040"}


def save(fig, output_dir, filename):
    path = Path(output_dir) / filename
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"Saved {path}")


def plot_latency_box(sustained_lat, burst_lat, output_dir):
    fig, ax = plt.subplots(figsize=(8, 6))
    bp = ax.boxplot(
        [sustained_lat, burst_lat],
        tick_labels=["Sustained\n(50 req/s)", "Burst\n(500 req/s)"],
        patch_artist=True,
        flierprops=dict(marker="o", markersize=3, alpha=0.3, linestyle="none"),
    )
    for patch, color in zip(bp["boxes"], [COLORS["sustained"], COLORS["burst"]]):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
    ax.set_title("End-to-End Latency Distribution", fontsize=12, fontweight="bold")
    ax.set_ylabel("Latency (ms)")
    ax.grid(axis="y", alpha=0.3)
    save(fig, output_dir, "latency_boxplot.png")


def plot_latency_percentiles(sustained_lat, burst_lat, output_dir):
    s = sorted(sustained_lat)
    b = sorted(burst_lat)
    s_p99 = s[int(len(s) * 0.99)]
    b_p99 = b[int(len(b) * 0.99)]

    fig, ax = plt.subplots(figsize=(6, 6))
    bars = ax.bar(["Sustained", "Burst"], [s_p99, b_p99],
                  color=[COLORS["sustained"], COLORS["burst"]], alpha=0.8, width=0.4)
    for bar, val in zip(bars, [s_p99, b_p99]):
        ax.text(bar.get_x() + bar.get_width() / 2, val + 1, f"{val:.0f}ms",
                ha="center", va="bottom", fontsize=11, fontweight="bold")
    ax.set_ylabel("Latency (ms)")
    ax.set_title("P99 End-to-End Latency", fontsize=12, fontweight="bold")
    ax.grid(axis="y", alpha=0.3)
    save(fig, output_dir, "latency_p99.png")


def plot_throughput(sustained_rows, burst_rows, output_dir):
    fig, axes = plt.subplots(1, 2, figsize=(14, 5), sharey=False)
    for ax, rows, label, color in [
        (axes[0], sustained_rows, "Sustained (50 req/s)", COLORS["sustained"]),
        (axes[1], burst_rows,     "Burst (500 req/s)",    COLORS["burst"]),
    ]:
        offsets, counts = throughput_series(rows, bucket_secs=5)
        ax.plot(offsets, counts, color=color, linewidth=1.5)
        ax.fill_between(offsets, counts, alpha=0.2, color=color)
        ax.set_title(label)
        ax.set_xlabel("Time since start (s)")
        ax.set_ylabel("Throughput (req/s)")
        ax.grid(axis="y", alpha=0.3)
    fig.suptitle("Throughput Over Time", fontsize=12, fontweight="bold")
    save(fig, output_dir, "throughput.png")


def plot_error_timeout(sustained_rows, burst_rows, output_dir):
    labels   = ["Sustained", "Burst"]
    profiles = [sustained_rows, burst_rows]
    colors   = [COLORS["sustained"], COLORS["burst"]]

    err_rates     = [error_rate(p)   for p in profiles]
    timeout_rates = [timeout_rate(p) for p in profiles]

    x = np.arange(len(labels))
    width = 0.35

    fig, ax = plt.subplots(figsize=(8, 5))
    bars1 = ax.bar(x - width / 2, err_rates,     width, label="Error rate (%)",   color=colors, alpha=0.7)
    bars2 = ax.bar(x + width / 2, timeout_rates, width, label="Timeout rate (%)", color=colors, alpha=0.4)

    for bar in list(bars1) + list(bars2):
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2, h + 0.02, f"{h:.2f}%",
                ha="center", va="bottom", fontsize=9)

    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Rate (%)")
    ax.set_title("Error Rate & Timeout Rate", fontsize=12, fontweight="bold")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    save(fig, output_dir, "error_timeout_rate.png")


def plot_exec_duration(sustained_dur, burst_dur, output_dir):
    fig, ax = plt.subplots(figsize=(8, 6))
    bp = ax.boxplot(
        [sustained_dur, burst_dur],
        tick_labels=["Sustained", "Burst"],
        patch_artist=True,
        flierprops=dict(marker="o", markersize=3, alpha=0.3, linestyle="none"),
    )
    for patch, color in zip(bp["boxes"], [COLORS["sustained"], COLORS["burst"]]):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
    ax.set_title("Lambda Execution Duration (CloudWatch)", fontsize=12, fontweight="bold")
    ax.set_ylabel("Duration (ms)")
    ax.grid(axis="y", alpha=0.3)
    save(fig, output_dir, "execution_duration_boxplot.png")


def print_summary(label, rows, exec_durations=None):
    m = measurement_rows(rows)
    lat = latencies(m)
    print(f"\n{'='*50}")
    print(f"{label.upper()}")
    print(f"{'='*50}")
    print(f"Measurement requests : {len(m)}")
    print(f"Successful (200)     : {len(lat)}")
    print(f"Error rate           : {error_rate(m):.2f}%")
    print(f"Timeout rate         : {timeout_rate(m):.2f}%")

    # Throughput
    ts = [float(r["timestamp_sent"]) for r in m if r.get("timestamp_sent")]
    if len(ts) > 1:
        duration_secs = max(ts) - min(ts)
        if duration_secs > 0:
            print(f"Throughput           : {len(lat) / duration_secs:.2f} req/s")

    # End-to-end latency
    if lat:
        print(f"End-to-end latency (ms):")
        print(f"  Min    : {min(lat):.2f}")
        print(f"  Mean   : {statistics.mean(lat):.2f}")
        print(f"  Median : {statistics.median(lat):.2f}")
        if len(lat) >= 100:
            q = sorted(lat)
            print(f"  P95    : {q[int(len(q)*0.95)]:.2f}")
            print(f"  P99    : {q[int(len(q)*0.99)]:.2f}")
        print(f"  Max    : {max(lat):.2f}")

    # Execution duration from CloudWatch
    if exec_durations:
        print(f"Execution duration (ms):")
        print(f"  Min    : {min(exec_durations):.2f}")
        print(f"  Mean   : {statistics.mean(exec_durations):.2f}")
        print(f"  Median : {statistics.median(exec_durations):.2f}")
        if len(exec_durations) >= 100:
            q = sorted(exec_durations)
            print(f"  P95    : {q[int(len(q)*0.95)]:.2f}")
            print(f"  P99    : {q[int(len(q)*0.99)]:.2f}")
        print(f"  Max    : {max(exec_durations):.2f}")


# ── Auto-discover CSVs ────────────────────────────────────────────────────────

def find_latest_csv(data_dir, profile):
    pattern = str(Path(data_dir) / f"results_*_{profile}_*.csv")
    matches = sorted(glob.glob(pattern))
    if not matches:
        return None
    return matches[-1]


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(description="Analyze Experiment 4 burst vs sustained results.")
    parser.add_argument("--sustained",   help="CSV from sustained run (auto-detected from data/experiment4/ if omitted)")
    parser.add_argument("--burst",       help="CSV from burst run (auto-detected from data/experiment4/ if omitted)")
    parser.add_argument("--data-dir",    default="data/experiment4", help="Where to look for CSVs if not specified directly")
    parser.add_argument("--output-dir",  default="plots/experiment4")
    parser.add_argument("--function",    help="Lambda function name for CloudWatch execution duration query")
    parser.add_argument("--region",      default="us-west-2")
    return parser.parse_args()


def main():
    args = parse_args()

    sustained_path = args.sustained or find_latest_csv(args.data_dir, "sustained")
    burst_path     = args.burst     or find_latest_csv(args.data_dir, "burst")

    if not sustained_path or not burst_path:
        print("Could not find sustained and burst CSVs. Specify --sustained / --burst or check --data-dir.")
        sys.exit(1)

    print(f"Sustained : {sustained_path}")
    print(f"Burst     : {burst_path}")

    sustained_rows = load_csv(sustained_path)
    burst_rows     = load_csv(burst_path)

    s_meas = measurement_rows(sustained_rows)
    b_meas = measurement_rows(burst_rows)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    s_lat = latencies(s_meas)
    b_lat = latencies(b_meas)

    if s_lat and b_lat:
        plot_latency_box(s_lat, b_lat, output_dir)
        plot_latency_percentiles(s_lat, b_lat, output_dir)
    else:
        print("Not enough latency data for plots.")

    plot_throughput(s_meas, b_meas, output_dir)
    plot_error_timeout(s_meas, b_meas, output_dir)

    s_dur, b_dur = None, None

    # Optional: CloudWatch execution duration — time windows derived from CSV timestamps
    if args.function:
        print(f"\nQuerying CloudWatch for execution duration ({args.function})...")

        def csv_window(rows):
            ts = [float(r["timestamp_sent"]) for r in rows if r.get("timestamp_sent")]
            if not ts:
                return None, None
            # Add a 60s buffer on each side so CloudWatch captures all REPORT lines
            start = datetime.fromtimestamp(min(ts) - 60, tz=timezone.utc)
            end   = datetime.fromtimestamp(max(ts) + 60, tz=timezone.utc)
            return start, end

        s_start, s_end = csv_window(sustained_rows)
        b_start, b_end = csv_window(burst_rows)

        s_dur = query_cloudwatch(args.function, s_start, s_end, args.region) if s_start else None
        b_dur = query_cloudwatch(args.function, b_start, b_end, args.region) if b_start else None

        if s_dur and b_dur:
            plot_exec_duration(s_dur, b_dur, output_dir)
        else:
            print("  Not enough CloudWatch data for execution duration plot.")
    else:
        print("\n(Skipping execution duration — pass --function <name> to enable CloudWatch query)")

    # Print summaries after CloudWatch data is available so execution duration is included
    print_summary("sustained", sustained_rows, exec_durations=s_dur)
    print_summary("burst",     burst_rows,     exec_durations=b_dur)

    print(f"\nAll plots saved to {output_dir}/")


if __name__ == "__main__":
    main()

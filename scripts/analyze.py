#!/usr/bin/env python3
"""
Pulls CloudWatch logs for Experiment 1 Lambda functions and generates
box plots, bar charts, and violin plots comparing execution duration,
memory used, and cost per invocation across all runtimes.

The first 1500 invocations per function are skipped (warmup phase).
Outliers are capped at the 99th percentile to keep plots readable.

Usage:
    python analyze.py --config scripts/functions.json --region us-west-2
"""

import argparse
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import boto3
import matplotlib.pyplot as plt
import numpy as np

# AWS Lambda pricing per GB-second
PRICE_X86 = 0.0000166667
PRICE_ARM  = 0.0000133334

WARMUP_REQUESTS = 1500  # skip the first N invocations per function

# Runtime colours
COLORS = {
    "python": "#3776AB",
    "go":     "#00ADD8",
    "java":   "#ED8B00",
}

FUNCTION_ORDER = [
    # "exp1-python-x86",
    # "exp1-python-arm",
    "exp1-go-x86",
    "exp1-go-arm",
    "exp1-java-x86",
    "exp1-java-arm",
]

LABELS = {
    # "exp1-python-x86": "Python\n(x86)",
    # "exp1-python-arm": "Python\n(ARM)",
    "exp1-go-x86":     "Go\n(x86)",
    "exp1-go-arm":     "Go\n(ARM)",
    "exp1-java-x86":   "Java\n(x86)",
    "exp1-java-arm":   "Java\n(ARM)",
}


def query_cloudwatch_logs(client, function_name, start_time, end_time):
    """Query CloudWatch Logs Insights for REPORT lines from a Lambda function."""
    log_group = f"/aws/lambda/{function_name}"
    query = (
        "filter @type = \"REPORT\"\n"
        "| fields @duration, @maxMemoryUsed, @memorySize, @billedDuration\n"
        "| sort @timestamp asc\n"
        "| limit 10000"
    )

    response = client.start_query(
        logGroupName=log_group,
        startTime=int(start_time.timestamp()),
        endTime=int(end_time.timestamp()),
        queryString=query,
    )
    query_id = response["queryId"]

    while True:
        result = client.get_query_results(queryId=query_id)
        if result["status"] == "Complete":
            break
        if result["status"] == "Failed":
            print(f"  Query failed for {function_name}")
            return []
        time.sleep(1)

    records = []
    for row in result["results"]:
        record = {}
        for field in row:
            record[field["field"]] = field["value"]
        records.append(record)

    return records


def compute_cost(billed_duration_ms, memory_size_mb, is_arm):
    """Compute cost per invocation in USD."""
    price      = PRICE_ARM if is_arm else PRICE_X86
    gb_seconds = (billed_duration_ms / 1000) * (memory_size_mb / 1024)
    return gb_seconds * price


def cap_outliers(values, percentile=99):
    """Cap values at the given percentile to suppress extreme outliers."""
    if not values:
        return values
    cap = np.percentile(values, percentile)
    return [min(v, cap) for v in values]


def collect_all_metrics(client, functions, start_time, end_time):
    """Collect metrics for all functions, skipping the first WARMUP_REQUESTS records."""
    data = {}
    for function_name in functions:
        print(f"Querying CloudWatch for {function_name}...")
        records = query_cloudwatch_logs(client, function_name, start_time, end_time)
        print(f"  Total records: {len(records)}  —  skipping first {WARMUP_REQUESTS} (warmup)")

        # Skip the first 1500 warmup invocations
        measurement_records = records[WARMUP_REQUESTS:]
        print(f"  Measurement records: {len(measurement_records)}")

        if not measurement_records:
            print(f"  WARNING: No measurement records remaining for {function_name}")
            continue

        is_arm      = "arm" in function_name
        durations   = []
        memory_used = []
        costs       = []

        for r in measurement_records:
            try:
                duration    = float(r.get("@duration", 0))
                max_mem_mb  = float(r.get("@maxMemoryUsed", 0)) / 1024 / 1024  # bytes → MB
                mem_size_mb = float(r.get("@memorySize", 0))   / 1024 / 1024  # bytes → MB
                billed      = float(r.get("@billedDuration", 0))

                durations.append(duration)
                memory_used.append(max_mem_mb)
                costs.append(compute_cost(billed, mem_size_mb, is_arm))

            except (ValueError, TypeError):
                continue

        if not durations:
            continue

        # Cap at 99th percentile so extreme outliers don't crush the plot scale
        data[function_name] = {
            "duration":    cap_outliers(durations),
            "memory_used": cap_outliers(memory_used),
            "cost":        cap_outliers(costs),
        }

    return data


def get_plot_series(data):
    """Return ordered labels, value lists, and colours for plotting."""
    labels = []
    series = {"duration": [], "memory_used": [], "cost": []}
    colors = []

    for fn in FUNCTION_ORDER:
        if fn not in data:
            continue
        labels.append(LABELS[fn])
        for key in series:
            series[key].append(data[fn][key])
        runtime = "python" if "python" in fn else ("go" if "go" in fn else "java")
        colors.append(COLORS[runtime])

    return labels, series, colors


def make_legend():
    from matplotlib.patches import Patch
    return [
        Patch(facecolor=COLORS["python"], alpha=0.7, label="Python"),
        Patch(facecolor=COLORS["go"],     alpha=0.7, label="Go"),
        Patch(facecolor=COLORS["java"],   alpha=0.7, label="Java"),
    ]


# ── Individual plot renderers ─────────────────────────────────────────────────

def plot_box(ax, plot_data, plot_labels, colors):
    bp = ax.boxplot(
        plot_data,
        tick_labels=plot_labels,
        patch_artist=True,
        flierprops=dict(marker="o", markersize=3, alpha=0.3, linestyle="none"),
    )
    for patch, color in zip(bp["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)


# ── Metric + plot type configuration ─────────────────────────────────────────

METRICS = [
    ("duration",    "Execution Duration (ms)", "duration"),
    ("memory_used", "Memory Used (MB)",         "memory_used"),
    ("cost",        "Cost per Invocation ($)",  "cost"),
]

PLOT_TYPES = [
    ("Box Plot",    plot_box,    "boxplot")
]


def plot_all(data, output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not data:
        print("No data to plot.")
        return

    labels, series, colors = get_plot_series(data)

    for metric_key, metric_title, metric_filename in METRICS:
        plot_data = series[metric_key]

        if not any(plot_data):
            print(f"No data for {metric_title}, skipping.")
            continue

        for plot_type_label, plot_fn, plot_filename in PLOT_TYPES:
            fig, ax = plt.subplots(figsize=(10, 6))

            plot_fn(ax, plot_data, labels, colors)

            ax.set_title(
                f"{metric_title} — {plot_type_label}\n",
                fontsize=12, fontweight="bold"
            )
            ax.set_ylabel(metric_title)
            ax.grid(axis="y", alpha=0.3)
            ax.legend(handles=make_legend(), loc="upper right")

            filename    = f"{metric_filename}_{plot_filename}.png"
            output_path = output_dir / filename
            fig.tight_layout()
            fig.savefig(output_path, dpi=150)
            plt.close(fig)
            print(f"Saved {output_path}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_time(value, now):
    if value.endswith("h"):
        return now - timedelta(hours=float(value[:-1]))
    if value.endswith("m"):
        return now - timedelta(minutes=float(value[:-1]))
    return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Pull CloudWatch logs and generate comparison plots for Experiment 1."
    )
    parser.add_argument("--config",     default="scripts/functions.json")
    parser.add_argument("--region",     default="us-west-2")
    parser.add_argument("--start",      default="1h")
    parser.add_argument("--end",        default="now")
    parser.add_argument("--output-dir", default="plots")
    return parser.parse_args()


def main():
    args = parse_args()

    with open(args.config) as f:
        functions = json.load(f)

    now        = datetime.now(timezone.utc)
    start_time = parse_time(args.start, now)
    end_time   = now if args.end == "now" else datetime.fromisoformat(args.end).replace(tzinfo=timezone.utc)

    print(f"Time range: {start_time.isoformat()} to {end_time.isoformat()} UTC\n")

    client = boto3.client("logs", region_name=args.region)
    data   = collect_all_metrics(client, functions.keys(), start_time, end_time)
    print()
    plot_all(data, args.output_dir)


if __name__ == "__main__":
    main()
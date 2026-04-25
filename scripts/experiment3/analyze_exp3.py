#!/usr/bin/env python3
"""
Generate box plots for Experiments 1, 2, and 3.

Experiment 1/2:
    - Usually uses phase == measurement
    - CSVs may already include cost_usd

Experiment 3:
    - Uses phase == cold or warm
    - CSVs are stored separately in:
        data/experiment3-cold
        data/experiment3-warm
    - cost_usd is calculated from billed_duration_ms and memory_size_mb if missing

Example usage:

    # Experiment 1
    python3 scripts/analyze.py \
        --config scripts/experiment1/functions.json \
        --data-dir data/experiment1 \
        --output-dir plots/experiment1

    # Experiment 2
    python3 scripts/analyze.py \
        --config scripts/experiment2/functions.json \
        --data-dir data/experiment2 \
        --output-dir plots/experiment2

    # Experiment 3 cold starts
    python scripts/analyze.py \
        --config scripts/experiment3/functions.json \
        --data-dir data/experiment3-cold \
        --output-dir plots/experiment3-cold \
        --phase cold

    # Experiment 3 warm starts
    python scripts/analyze.py \
        --config scripts/experiment3/functions.json \
        --data-dir data/experiment3-warm \
        --output-dir plots/experiment3-warm \
        --phase warm
"""

import argparse
import csv
import glob
import json
import statistics
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


# ── Appearance ────────────────────────────────────────────────────────────────

COLORS = {
    "python": "#3776AB",
    "go": "#00ADD8",
    "java": "#ED8B00",
}

EXP1_ORDER = [
    "exp1-python-x86", "exp1-python-arm",
    "exp1-go-x86", "exp1-go-arm",
    "exp1-java-x86", "exp1-java-arm",
]

EXP2_ORDER = [
    "exp2-java-x86-128", "exp2-java-arm-128",
    "exp2-java-x86-1024", "exp2-java-arm-1024",
    "exp2-java-x86-1769", "exp2-java-arm-1769",
    "exp2-java-x86-3008", "exp2-java-arm-3008",
]

EXP3_ORDER = [
    "exp3-python-x86",
    "exp3-go-x86",
    "exp3-java-x86",
]

LABELS = {
    # Experiment 1
    "exp1-python-x86": "Python\n(x86)",
    "exp1-python-arm": "Python\n(ARM)",
    "exp1-go-x86": "Go\n(x86)",
    "exp1-go-arm": "Go\n(ARM)",
    "exp1-java-x86": "Java\n(x86)",
    "exp1-java-arm": "Java\n(ARM)",

    # Experiment 2
    "exp2-java-x86-128": "x86\n128 MB",
    "exp2-java-arm-128": "ARM\n128 MB",
    "exp2-java-x86-1024": "x86\n1024 MB",
    "exp2-java-arm-1024": "ARM\n1024 MB",
    "exp2-java-x86-1769": "x86\n1769 MB",
    "exp2-java-arm-1769": "ARM\n1769 MB",
    "exp2-java-x86-3008": "x86\n3008 MB",
    "exp2-java-arm-3008": "ARM\n3008 MB",

    # Experiment 3
    "exp3-python-x86": "Python\n(x86)",
    "exp3-go-x86": "Go\n(x86)",
    "exp3-java-x86": "Java\n(x86)",
}


# AWS Lambda x86 default pricing approximation.
# Change these if your report uses a different pricing model.
REQUEST_COST_USD = 0.20 / 1_000_000
GB_SECOND_COST_USD = 0.0000166667


def runtime_color(function_name):
    if "python" in function_name:
        return COLORS["python"]
    if "go" in function_name:
        return COLORS["go"]
    return COLORS["java"]


def make_legend(functions):
    from matplotlib.patches import Patch

    runtimes = set()

    for fn in functions:
        if "python" in fn:
            runtimes.add("python")
        elif "go" in fn:
            runtimes.add("go")
        elif "java" in fn:
            runtimes.add("java")

    return [
        Patch(facecolor=COLORS[r], alpha=0.7, label=r.capitalize())
        for r in sorted(runtimes)
    ]


# ── CSV discovery ─────────────────────────────────────────────────────────────

def find_latest_csv(data_dir, label):
    """
    Supports both:
        results_exp3-go-x86.csv
        results_exp3-go-x86_exp3.csv
        results_exp3-go-x86_exp3_20260424.csv
    """
    data_dir = Path(data_dir)

    exact_patterns = [
        data_dir / f"results_{label}.csv",
        data_dir / f"results_{label}_exp3.csv",
    ]

    for path in exact_patterns:
        if path.exists():
            return str(path)

    matches = sorted(glob.glob(str(data_dir / f"results_{label}*.csv")))
    return matches[-1] if matches else None


def discover_functions_from_csvs(data_dir):
    """
    Allows the script to work even if --config is not provided.
    Reads function names from files like:
        results_exp3-go-x86_exp3.csv
    """
    functions = []

    for path in sorted(Path(data_dir).glob("results_*.csv")):
        name = path.name

        name = name.removeprefix("results_")
        name = name.removesuffix(".csv")

        # Clean common suffixes.
        if name.endswith("_exp3"):
            name = name.removesuffix("_exp3")

        functions.append(name)

    return functions


def determine_order(functions):
    if all("exp1" in fn for fn in functions):
        return [fn for fn in EXP1_ORDER if fn in functions]

    if all("exp2" in fn for fn in functions):
        return [fn for fn in EXP2_ORDER if fn in functions]

    if all("exp3" in fn for fn in functions):
        return [fn for fn in EXP3_ORDER if fn in functions]

    return functions


# ── Data loading ──────────────────────────────────────────────────────────────

def safe_float(value):
    if value is None or value == "":
        return None

    try:
        return float(value)
    except ValueError:
        return None


def calculate_cost_usd(row):
    """
    If cost_usd exists, use it.
    Otherwise calculate an approximate Lambda invocation cost using:
        cost = request cost + compute cost

    compute cost = billed duration in seconds * memory in GB * GB-second price
    """
    existing_cost = safe_float(row.get("cost_usd"))

    if existing_cost is not None:
        return existing_cost

    billed_duration_ms = safe_float(row.get("billed_duration_ms"))
    memory_size_mb = safe_float(row.get("memory_size_mb"))

    if billed_duration_ms is None or memory_size_mb is None:
        return None

    billed_seconds = billed_duration_ms / 1000
    memory_gb = memory_size_mb / 1024

    compute_cost = billed_seconds * memory_gb * GB_SECOND_COST_USD
    return REQUEST_COST_USD + compute_cost


def should_keep_row(row, requested_phase):
    """
    Experiment 1/2:
        phase is usually measurement

    Experiment 3:
        phase is cold or warm

    If --phase is provided, only keep matching rows.
    If --phase is not provided, keep successful measurement/cold/warm rows.
    """
    row_phase = row.get("phase", "").strip().lower()

    if requested_phase:
        return row_phase == requested_phase.lower()

    return row_phase in {"measurement", "cold", "warm"}


def is_successful_row(row):
    status = row.get("http_status", "")
    error = row.get("error", "")
    is_timeout = row.get("is_timeout", "")

    if status and status != "200":
        return False

    if error:
        return False

    if str(is_timeout).lower() == "true":
        return False

    return True


def load_metrics(data_dir, label, phase=None):
    path = find_latest_csv(data_dir, label)

    if not path:
        print(f"  No CSV found for {label}")
        return None

    durations = []
    latencies = []
    init_durations = []
    billed_durations = []
    memory_used = []
    costs = []

    total_rows = 0
    kept_rows = 0
    skipped_rows = 0

    with open(path, newline="") as f:
        reader = csv.DictReader(f)

        for row in reader:
            total_rows += 1

            if not should_keep_row(row, phase):
                skipped_rows += 1
                continue

            if not is_successful_row(row):
                skipped_rows += 1
                continue

            execution_ms = safe_float(row.get("execution_ms"))
            latency_ms = safe_float(row.get("latency_ms"))
            init_duration_ms = safe_float(row.get("init_duration_ms"))
            billed_duration_ms = safe_float(row.get("billed_duration_ms"))
            memory_mb = safe_float(row.get("memory_used_mb"))
            cost_usd = calculate_cost_usd(row)

            if execution_ms is None:
                skipped_rows += 1
                continue

            durations.append(execution_ms)

            if latency_ms is not None:
                latencies.append(latency_ms)

            if init_duration_ms is not None:
                init_durations.append(init_duration_ms)

            if billed_duration_ms is not None:
                billed_durations.append(billed_duration_ms)

            if memory_mb is not None:
                memory_used.append(memory_mb)

            if cost_usd is not None:
                costs.append(cost_usd)

            kept_rows += 1

    if not durations:
        print(f"  No usable rows for {label} in {Path(path).name}")
        return None

    print(
        f"  {label}: {kept_rows} usable rows from {Path(path).name} "
        f"({skipped_rows} skipped, {total_rows} total)"
    )

    return {
        "label": label,
        "path": path,
        "durations": durations,
        "latencies": latencies,
        "init_durations": init_durations,
        "billed_durations": billed_durations,
        "memory_used": memory_used,
        "costs": costs,
    }


def cap_outliers(values, percentile=99):
    if not values:
        return values

    cap = np.percentile(values, percentile)
    return [min(v, cap) for v in values]


# ── Plotting ──────────────────────────────────────────────────────────────────

def plot_metric(labels, data_series, colors, title, ylabel, output_path, legend_handles):
    if not data_series:
        return

    fig, ax = plt.subplots(figsize=(max(8, len(labels) * 1.4), 6))

    bp = ax.boxplot(
        data_series,
        tick_labels=labels,
        patch_artist=True,
        flierprops=dict(
            marker="o",
            markersize=3,
            alpha=0.3,
            linestyle="none",
        ),
    )

    for patch, color in zip(bp["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)

    ax.set_title(title, fontsize=12, fontweight="bold")
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", alpha=0.3)

    if legend_handles:
        ax.legend(handles=legend_handles, loc="upper right")

    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)

    print(f"Saved {output_path}")


def print_metric_summary(name, values, precision=2):
    if not values:
        print(f"    {name:<20} — no data")
        return

    sorted_values = sorted(values)
    p95 = np.percentile(values, 95)
    p99 = np.percentile(values, 99)

    print(
        f"    {name:<20} — "
        f"mean: {statistics.mean(values):.{precision}f}  "
        f"median: {statistics.median(values):.{precision}f}  "
        f"p95: {p95:.{precision}f}  "
        f"p99: {p99:.{precision}f}  "
        f"max: {sorted_values[-1]:.{precision}f}"
    )


def print_summary(metrics):
    label = metrics["label"]

    print(f"\n  {label}")
    print_metric_summary("Execution ms", metrics["durations"])
    print_metric_summary("Latency ms", metrics["latencies"])
    print_metric_summary("Init duration ms", metrics["init_durations"])
    print_metric_summary("Billed duration ms", metrics["billed_durations"])
    print_metric_summary("Memory used MB", metrics["memory_used"])
    print_metric_summary("Cost USD", metrics["costs"], precision=10)


def write_summary_csv(output_dir, all_metrics):
    output_path = Path(output_dir) / "summary.csv"

    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f)

        writer.writerow([
            "function",
            "rows",
            "execution_mean_ms",
            "execution_median_ms",
            "execution_p95_ms",
            "execution_p99_ms",
            "latency_mean_ms",
            "latency_median_ms",
            "latency_p95_ms",
            "latency_p99_ms",
            "init_duration_mean_ms",
            "init_duration_median_ms",
            "init_duration_p95_ms",
            "init_duration_p99_ms",
            "memory_used_mean_mb",
            "cost_mean_usd",
        ])

        for m in all_metrics:
            durations = m["durations"]
            latencies = m["latencies"]
            init_durations = m["init_durations"]
            memory_used = m["memory_used"]
            costs = m["costs"]

            writer.writerow([
                m["label"],
                len(durations),

                statistics.mean(durations) if durations else "",
                statistics.median(durations) if durations else "",
                np.percentile(durations, 95) if durations else "",
                np.percentile(durations, 99) if durations else "",

                statistics.mean(latencies) if latencies else "",
                statistics.median(latencies) if latencies else "",
                np.percentile(latencies, 95) if latencies else "",
                np.percentile(latencies, 99) if latencies else "",

                statistics.mean(init_durations) if init_durations else "",
                statistics.median(init_durations) if init_durations else "",
                np.percentile(init_durations, 95) if init_durations else "",
                np.percentile(init_durations, 99) if init_durations else "",

                statistics.mean(memory_used) if memory_used else "",
                statistics.mean(costs) if costs else "",
            ])

    print(f"Saved {output_path}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Plot Lambda experiment metrics from enriched CSVs."
    )

    parser.add_argument(
        "--config",
        required=False,
        help="Path to functions.json. Optional for Experiment 3 if CSVs are discoverable.",
    )

    parser.add_argument(
        "--data-dir",
        required=True,
        help="Directory containing CSV files.",
    )

    parser.add_argument(
        "--output-dir",
        default="plots",
        help="Directory where plots and summary.csv will be saved.",
    )

    parser.add_argument(
        "--phase",
        required=False,
        choices=["measurement", "cold", "warm"],
        help="Optional phase filter. Use cold or warm for Experiment 3.",
    )

    parser.add_argument(
        "--cap-percentile",
        type=float,
        default=99,
        help="Percentile used to cap outliers in plots only. Default: 99.",
    )

    args = parser.parse_args()

    if args.config:
        with open(args.config) as f:
            functions = list(json.load(f).keys())
    else:
        functions = discover_functions_from_csvs(args.data_dir)

    order = determine_order(functions)

    print(f"Loading CSVs from {args.data_dir}...")

    if args.phase:
        print(f"Filtering rows to phase = {args.phase}")

    all_metrics = []

    for fn in order:
        metrics = load_metrics(args.data_dir, fn, phase=args.phase)

        if metrics is None:
            continue

        all_metrics.append(metrics)
        print_summary(metrics)

    if not all_metrics:
        print("\nNo data to plot.")
        return

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    labels = [LABELS.get(m["label"], m["label"]) for m in all_metrics]
    colors = [runtime_color(m["label"]) for m in all_metrics]
    legend = make_legend(order)

    duration_series = [
        cap_outliers(m["durations"], args.cap_percentile)
        for m in all_metrics
    ]

    latency_series = [
        cap_outliers(m["latencies"], args.cap_percentile)
        for m in all_metrics
        if m["latencies"]
    ]

    latency_labels = [
        LABELS.get(m["label"], m["label"])
        for m in all_metrics
        if m["latencies"]
    ]

    latency_colors = [
        runtime_color(m["label"])
        for m in all_metrics
        if m["latencies"]
    ]

    init_series = [
        cap_outliers(m["init_durations"], args.cap_percentile)
        for m in all_metrics
        if m["init_durations"]
    ]

    init_labels = [
        LABELS.get(m["label"], m["label"])
        for m in all_metrics
        if m["init_durations"]
    ]

    init_colors = [
        runtime_color(m["label"])
        for m in all_metrics
        if m["init_durations"]
    ]

    memory_series = [
        cap_outliers(m["memory_used"], args.cap_percentile)
        for m in all_metrics
        if m["memory_used"]
    ]

    memory_labels = [
        LABELS.get(m["label"], m["label"])
        for m in all_metrics
        if m["memory_used"]
    ]

    memory_colors = [
        runtime_color(m["label"])
        for m in all_metrics
        if m["memory_used"]
    ]

    cost_series = [
        cap_outliers(m["costs"], args.cap_percentile)
        for m in all_metrics
        if m["costs"]
    ]

    cost_labels = [
        LABELS.get(m["label"], m["label"])
        for m in all_metrics
        if m["costs"]
    ]

    cost_colors = [
        runtime_color(m["label"])
        for m in all_metrics
        if m["costs"]
    ]

    phase_suffix = f" — {args.phase.capitalize()}" if args.phase else ""

    plot_metric(
        labels,
        duration_series,
        colors,
        f"Execution Duration (ms){phase_suffix}",
        "Execution Duration (ms)",
        output_dir / "execution_duration_boxplot.png",
        legend,
    )

    plot_metric(
        latency_labels,
        latency_series,
        latency_colors,
        f"End-to-End Latency (ms){phase_suffix}",
        "Latency (ms)",
        output_dir / "latency_boxplot.png",
        legend,
    )

    plot_metric(
        init_labels,
        init_series,
        init_colors,
        f"Init Duration (ms){phase_suffix}",
        "Init Duration (ms)",
        output_dir / "init_duration_boxplot.png",
        legend,
    )

    plot_metric(
        memory_labels,
        memory_series,
        memory_colors,
        f"Memory Used (MB){phase_suffix}",
        "Memory Used (MB)",
        output_dir / "memory_used_boxplot.png",
        legend,
    )

    plot_metric(
        cost_labels,
        cost_series,
        cost_colors,
        f"Cost per Invocation ($){phase_suffix}",
        "Cost per Invocation ($)",
        output_dir / "cost_per_invocation_boxplot.png",
        legend,
    )

    write_summary_csv(output_dir, all_metrics)

    print(f"\nAll plots and summary saved to {output_dir}/")


if __name__ == "__main__":
    main()
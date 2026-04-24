#!/usr/bin/env python3
"""
Generate box plots for Experiments 1 and 2 from enriched CSVs.

Reads execution_ms, memory_used_mb, and cost_usd columns added by enrich_csv.py.
Only measurement-phase rows (phase == "measurement") are used.

Usage:
    # Experiment 1
    python3 scripts/analyze.py --config scripts/experiment1/functions.json \
        --data-dir data/experiment1 --output-dir plots/experiment1

    # Experiment 2
    python3 scripts/analyze.py --config scripts/experiment2/functions.json \
        --data-dir data/experiment2 --output-dir plots/experiment2
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
    "go":     "#00ADD8",
    "java":   "#ED8B00",
}

EXP1_ORDER = [
    "exp1-python-x86", "exp1-python-arm",
    "exp1-go-x86",     "exp1-go-arm",
    "exp1-java-x86",   "exp1-java-arm",
]

EXP2_ORDER = [
    "exp2-java-x86-128",  "exp2-java-arm-128",
    "exp2-java-x86-1024", "exp2-java-arm-1024",
    "exp2-java-x86-1769", "exp2-java-arm-1769",
    "exp2-java-x86-3008", "exp2-java-arm-3008",
]

LABELS = {
    "exp1-python-x86":  "Python\n(x86)",
    "exp1-python-arm":  "Python\n(ARM)",
    "exp1-go-x86":      "Go\n(x86)",
    "exp1-go-arm":      "Go\n(ARM)",
    "exp1-java-x86":    "Java\n(x86)",
    "exp1-java-arm":    "Java\n(ARM)",
    "exp2-java-x86-128":  "x86\n128 MB",
    "exp2-java-arm-128":  "ARM\n128 MB",
    "exp2-java-x86-1024": "x86\n1024 MB",
    "exp2-java-arm-1024": "ARM\n1024 MB",
    "exp2-java-x86-1769": "x86\n1769 MB",
    "exp2-java-arm-1769": "ARM\n1769 MB",
    "exp2-java-x86-3008": "x86\n3008 MB",
    "exp2-java-arm-3008": "ARM\n3008 MB",
}


def runtime_color(fn):
    if "python" in fn:
        return COLORS["python"]
    if "go" in fn:
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
        else:
            runtimes.add("java")
    return [Patch(facecolor=COLORS[r], alpha=0.7, label=r.capitalize()) for r in sorted(runtimes)]


# ── Data loading ──────────────────────────────────────────────────────────────

def find_latest_csv(data_dir, label):
    exact = Path(data_dir) / f"results_{label}.csv"
    if exact.exists():
        return str(exact)
    matches = sorted(glob.glob(str(Path(data_dir) / f"results_{label}_*.csv")))
    return matches[-1] if matches else None


def load_metrics(data_dir, label):
    path = find_latest_csv(data_dir, label)
    if not path:
        print(f"  No CSV found for {label}")
        return None, None, None

    durations   = []
    memory_used = []
    costs       = []

    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            if row.get("phase") != "measurement":
                continue
            if not row.get("execution_ms"):
                continue
            try:
                durations.append(float(row["execution_ms"]))
                memory_used.append(float(row["memory_used_mb"]))
                costs.append(float(row["cost_usd"]))
            except (ValueError, TypeError):
                continue

    if not durations:
        print(f"  No enriched measurement rows for {label} in {path}")
        return None, None, None

    print(f"  {label}: {len(durations)} measurement rows from {Path(path).name}")
    return durations, memory_used, costs


def cap_outliers(values, percentile=99):
    if not values:
        return values
    cap = np.percentile(values, percentile)
    return [min(v, cap) for v in values]


# ── Plotting ──────────────────────────────────────────────────────────────────

def plot_metric(labels, data_series, colors, title, ylabel, output_path, legend_handles):
    fig, ax = plt.subplots(figsize=(max(8, len(labels) * 1.4), 6))
    bp = ax.boxplot(
        data_series,
        tick_labels=labels,
        patch_artist=True,
        flierprops=dict(marker="o", markersize=3, alpha=0.3, linestyle="none"),
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


def print_summary(label, durations, memory_used, costs):
    print(f"\n  {label}")
    print(f"    Execution (ms) — mean: {statistics.mean(durations):.2f}  "
          f"median: {statistics.median(durations):.2f}  "
          f"p99: {sorted(durations)[int(len(durations)*0.99)]:.2f}")
    print(f"    Memory (MB)    — mean: {statistics.mean(memory_used):.2f}")
    print(f"    Cost (USD)     — mean: {statistics.mean(costs):.8f}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Plot Experiment 1/2 metrics from enriched CSVs.")
    parser.add_argument("--config",     required=True, help="Path to functions.json")
    parser.add_argument("--data-dir",   required=True, help="Directory containing enriched CSVs")
    parser.add_argument("--output-dir", default="plots")
    args = parser.parse_args()

    with open(args.config) as f:
        functions = list(json.load(f).keys())

    # Determine ordering
    if all("exp1" in fn for fn in functions):
        order = [fn for fn in EXP1_ORDER if fn in functions]
    elif all("exp2" in fn for fn in functions):
        order = [fn for fn in EXP2_ORDER if fn in functions]
    else:
        order = functions

    print(f"Loading enriched CSVs from {args.data_dir}...")
    labels, dur_series, mem_series, cost_series, colors = [], [], [], [], []

    for fn in order:
        dur, mem, cost = load_metrics(args.data_dir, fn)
        if dur is None:
            continue
        labels.append(LABELS.get(fn, fn))
        dur_series.append(cap_outliers(dur))
        mem_series.append(cap_outliers(mem))
        cost_series.append(cap_outliers(cost))
        colors.append(runtime_color(fn))
        print_summary(fn, dur, mem, cost)

    if not labels:
        print("\nNo data to plot — run enrich_csv.py first.")
        return

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    legend = make_legend(order)

    plot_metric(labels, dur_series,  colors, "Execution Duration (ms) — Box Plot",
                "Duration (ms)",          output_dir / "execution_duration_boxplot.png", legend)
    plot_metric(labels, mem_series,  colors, "Memory Used (MB) — Box Plot",
                "Memory Used (MB)",        output_dir / "memory_used_boxplot.png",        legend)
    plot_metric(labels, cost_series, colors, "Cost per Invocation ($) — Box Plot",
                "Cost per Invocation ($)", output_dir / "cost_per_invocation_boxplot.png", legend)

    print(f"\nAll plots saved to {output_dir}/")


if __name__ == "__main__":
    main()

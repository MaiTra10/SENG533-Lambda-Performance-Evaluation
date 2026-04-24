#!/usr/bin/env python3
"""
Enrich a load_test.py CSV with server-side metrics from CloudWatch:
  execution_ms, memory_used_mb, cost_usd

Joins on lambda_request_id (x-amzn-requestid header captured during the run).

Usage:
    python3 scripts/enrich_csv.py \
        --csv data/experiment1/results_exp1-python-x86_<ts>.csv \
        --function exp1-python-x86 \
        --region us-west-2

    # Enrich all CSVs in a directory
    python3 scripts/enrich_csv.py \
        --dir data/experiment1 \
        --config scripts/experiment1/functions.json \
        --region us-west-2
"""

import argparse
import csv
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import boto3

PRICE_X86 = 0.0000166667   # USD per GB-second
PRICE_ARM  = 0.0000133334


def query_cloudwatch(client, function_name, start_time, end_time):
    log_group = f"/aws/lambda/{function_name}"
    query = (
        "filter @type = \"REPORT\"\n"
        "| fields @requestId, @duration, @maxMemoryUsed, @memorySize, @billedDuration\n"
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
            print(f"  CloudWatch query failed for {function_name}")
            return {}
        time.sleep(1)

    records = {}
    for row in result["results"]:
        r = {f["field"]: f["value"] for f in row}
        rid = r.get("@requestId", "").strip()
        if rid:
            records[rid] = r
    return records


def compute_cost(billed_duration_ms, memory_size_mb, is_arm):
    price = PRICE_ARM if is_arm else PRICE_X86
    return (float(billed_duration_ms) / 1000) * (float(memory_size_mb) / 1024) * price


def enrich(csv_path, function_name, region):
    csv_path = Path(csv_path)
    print(f"\nEnriching {csv_path.name} ({function_name})...")

    with open(csv_path, newline="") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        print("  Empty CSV, skipping.")
        return

    if "lambda_request_id" not in rows[0]:
        print("  No lambda_request_id column — re-run the load test to capture request IDs.")
        return

    # Derive time window from CSV timestamps
    timestamps = [float(r["timestamp_sent"]) for r in rows if r.get("timestamp_sent")]
    if not timestamps:
        print("  No timestamps found.")
        return

    start_time = datetime.fromtimestamp(min(timestamps) - 60, tz=timezone.utc)
    end_time   = datetime.fromtimestamp(max(timestamps) + 60, tz=timezone.utc)

    client  = boto3.client("logs", region_name=region)
    cw_data = query_cloudwatch(client, function_name, start_time, end_time)
    print(f"  CloudWatch returned {len(cw_data)} REPORT records")

    is_arm  = "arm" in function_name
    matched = 0

    for row in rows:
        rid = row.get("lambda_request_id", "").strip()
        cw  = cw_data.get(rid)
        if cw:
            try:
                duration    = float(cw.get("@duration", 0))
                # CloudWatch returns @maxMemoryUsed and @memorySize in bytes
                max_mem_mb  = float(cw.get("@maxMemoryUsed", 0)) / 1024 / 1024
                mem_size_mb = float(cw.get("@memorySize", 0))   / 1024 / 1024
                billed      = float(cw.get("@billedDuration", 0))
                row["execution_ms"]   = f"{duration:.3f}"
                row["memory_used_mb"] = f"{max_mem_mb:.3f}"
                row["cost_usd"]       = f"{compute_cost(billed, mem_size_mb, is_arm):.10f}"
                matched += 1
            except (ValueError, TypeError):
                pass
        if "execution_ms" not in row:
            row["execution_ms"]   = ""
            row["memory_used_mb"] = ""
            row["cost_usd"]       = ""

    print(f"  Matched {matched}/{len(rows)} rows ({matched/len(rows)*100:.1f}%)")

    # Write enriched CSV (overwrites original)
    fieldnames = list(rows[0].keys())
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"  Saved enriched CSV to {csv_path}")


def main():
    parser = argparse.ArgumentParser(description="Enrich load test CSVs with CloudWatch server-side metrics.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--csv",      help="Single CSV file to enrich")
    group.add_argument("--dir",      help="Directory of CSVs to enrich (requires --config)")
    parser.add_argument("--function", help="Lambda function name (required with --csv)")
    parser.add_argument("--config",   help="functions.json mapping labels to URLs (required with --dir)")
    parser.add_argument("--region",   default="us-west-2")
    args = parser.parse_args()

    if args.csv:
        if not args.function:
            print("--function is required with --csv")
            sys.exit(1)
        enrich(args.csv, args.function, args.region)

    else:
        if not args.config:
            print("--config is required with --dir")
            sys.exit(1)
        with open(args.config) as f:
            functions = json.load(f)

        data_dir = Path(args.dir)
        for label in functions:
            matches = sorted(data_dir.glob(f"results_{label}_*.csv"))
            if not matches:
                print(f"No CSV found for {label} in {data_dir}")
                continue
            for csv_path in matches:
                enrich(csv_path, label, args.region)


if __name__ == "__main__":
    main()

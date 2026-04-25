#!/usr/bin/env python3

import argparse
import csv
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import boto3

PRICE_X86 = 0.0000166667
PRICE_ARM = 0.0000133334


def run_query(client, log_group, start_time, end_time):
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
            return {}
        time.sleep(1)

    records = {}
    for row in result["results"]:
        r = {f["field"]: f["value"] for f in row}
        rid = r.get("@requestId", "").strip()
        if rid:
            records[rid] = r

    return records


def query_cloudwatch(client, function_name, start_time, end_time):
    log_group = f"/aws/lambda/{function_name}"

    print(f"  Querying log group: {log_group}") 

    chunk_secs = 15

    records = {}
    chunk_start = start_time
    chunk_count = 0

    while chunk_start < end_time:
        chunk_end = min(chunk_start + timedelta(seconds=chunk_secs), end_time)

        chunk_records = run_query(client, log_group, chunk_start, chunk_end)
        records.update(chunk_records)

        chunk_count += 1
        chunk_start = chunk_end

    print(f"  ({chunk_count} queries, {len(records)} total records retrieved)")
    return records


def compute_cost(billed_ms, memory_mb, is_arm):
    price = PRICE_ARM if is_arm else PRICE_X86
    return (float(billed_ms) / 1000) * (float(memory_mb) / 1024) * price


def enrich_file(csv_path, region):
    print(f"\nEnriching {csv_path.name}...")

    function_name = csv_path.stem  
    is_arm = "arm" in function_name

    with open(csv_path, newline="") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        print("  Empty CSV, skipping.")
        return

    if "lambda_request_id" not in rows[0]:
        print("  Missing lambda_request_id column.")
        return

    timestamps = [float(r["timestamp_sent"]) for r in rows if r.get("timestamp_sent")]
    if not timestamps:
        print("  No timestamps found.")
        return

    start_time = datetime.fromtimestamp(min(timestamps) - 300, tz=timezone.utc)
    end_time   = datetime.fromtimestamp(max(timestamps) + 300, tz=timezone.utc)

    client = boto3.client("logs", region_name=region)

    cw_data = query_cloudwatch(client, function_name, start_time, end_time)

    matched = 0

    for row in rows:
        rid = row.get("lambda_request_id", "").strip()
        cw = cw_data.get(rid)

        if cw:
            try:
                duration = float(cw.get("@duration", 0))
                max_mem_mb = float(cw.get("@maxMemoryUsed", 0)) / 1024 / 1024
                mem_size_mb = float(cw.get("@memorySize", 0)) / 1024 / 1024
                billed = float(cw.get("@billedDuration", 0))

                row["execution_ms"] = f"{duration:.3f}"
                row["memory_used_mb"] = f"{max_mem_mb:.3f}"
                row["cost_usd"] = f"{compute_cost(billed, mem_size_mb, is_arm):.10f}"

                matched += 1
            except:
                pass

        if "execution_ms" not in row:
            row["execution_ms"] = ""
            row["memory_used_mb"] = ""
            row["cost_usd"] = ""

    print(f"  Matched {matched}/{len(rows)} rows ({matched/len(rows)*100:.1f}%)")

    fieldnames = list(rows[0].keys())

    output_path = csv_path.with_name(csv_path.stem + "_enriched.csv")

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"  Saved {output_path.name}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", required=True)
    parser.add_argument("--region", default="us-west-2")

    args = parser.parse_args()

    data_dir = Path(args.dir)

    csv_files = sorted(data_dir.glob("*.csv"))

    if not csv_files:
        print("No CSV files found.")
        return

    print(f"Found {len(csv_files)} CSV files")

    for csv_path in csv_files:
        enrich_file(csv_path, args.region)

    print("\nAll files enriched.")


if __name__ == "__main__":
    main()
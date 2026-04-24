#!/usr/bin/env python3

"""
Enrich Experiment 3 CSVs with CloudWatch REPORT metrics.

Adds:
  - execution_ms
  - init_duration_ms
  - billed_duration_ms
  - memory_used_mb
  - memory_size_mb

The join key is:
  CSV lambda_request_id == CloudWatch @requestId
"""

import argparse
import csv
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import boto3


def _run_query(client, log_group, start_time, end_time):
    query = (
        'filter @type = "REPORT"\n'
        "| fields @requestId, @duration, @initDuration, @billedDuration, @maxMemoryUsed, @memorySize\n"
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

        if result["status"] in ["Failed", "Cancelled", "Timeout"]:
            print(f"CloudWatch query ended with status: {result['status']}")
            return {}

        time.sleep(1)

    records = {}

    for row in result["results"]:
        record = {field["field"]: field["value"] for field in row}
        request_id = record.get("@requestId", "").strip()

        if request_id:
            records[request_id] = record

    return records


def query_cloudwatch(client, function_name, start_time, end_time):
    log_group = f"/aws/lambda/{function_name}"

    total_seconds = max(1, (end_time - start_time).total_seconds())

    # Keep chunks small enough to avoid the 10,000 row Logs Insights limit.
    # For 5000 observations, 4 chunks is normally enough.
    chunk_seconds = max(60, total_seconds / 4)

    all_records = {}
    chunk_start = start_time
    chunk_count = 0

    while chunk_start < end_time:
        chunk_end = min(chunk_start + timedelta(seconds=chunk_seconds), end_time)

        print(
            f"  Querying {log_group}: "
            f"{chunk_start.isoformat()} to {chunk_end.isoformat()}"
        )

        chunk_records = _run_query(
            client=client,
            log_group=log_group,
            start_time=chunk_start,
            end_time=chunk_end,
        )

        all_records.update(chunk_records)

        chunk_count += 1
        chunk_start = chunk_end

    print(f"  CloudWatch chunks queried: {chunk_count}")
    print(f"  REPORT records found     : {len(all_records)}")

    return all_records


def safe_float(value):
    if value is None or value == "":
        return None

    try:
        return float(value)
    except ValueError:
        return None


def enrich_csv(csv_path, function_name, region):
    csv_path = Path(csv_path)

    print()
    print("=" * 90)
    print(f"Enriching CSV : {csv_path}")
    print(f"Function name : {function_name}")
    print(f"Region        : {region}")
    print("=" * 90)

    with open(csv_path, newline="") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        print("CSV is empty. Skipping.")
        return

    if "lambda_request_id" not in rows[0]:
        print("CSV has no lambda_request_id column. Skipping.")
        return

    timestamps = [
        float(row["timestamp_sent"])
        for row in rows
        if row.get("timestamp_sent")
    ]

    if not timestamps:
        print("No timestamps found. Skipping.")
        return

    start_time = datetime.fromtimestamp(min(timestamps) - 180, tz=timezone.utc)
    end_time = datetime.fromtimestamp(max(timestamps) + 180, tz=timezone.utc)

    client = boto3.client("logs", region_name=region)
    cloudwatch_records = query_cloudwatch(client, function_name, start_time, end_time)

    matched = 0

    for row in rows:
        request_id = row.get("lambda_request_id", "").strip()
        cw = cloudwatch_records.get(request_id)

        row["execution_ms"] = ""
        row["init_duration_ms"] = ""
        row["billed_duration_ms"] = ""
        row["memory_used_mb"] = ""
        row["memory_size_mb"] = ""

        if not cw:
            continue

        duration = safe_float(cw.get("@duration"))
        init_duration = safe_float(cw.get("@initDuration"))
        billed_duration = safe_float(cw.get("@billedDuration"))
        max_memory_used = safe_float(cw.get("@maxMemoryUsed"))
        memory_size = safe_float(cw.get("@memorySize"))

        if duration is not None:
            row["execution_ms"] = f"{duration:.3f}"

        if init_duration is not None:
            row["init_duration_ms"] = f"{init_duration:.3f}"

        if billed_duration is not None:
            row["billed_duration_ms"] = f"{billed_duration:.3f}"

        # CloudWatch Logs Insights returns memory in bytes for these parsed fields.
        if max_memory_used is not None:
            row["memory_used_mb"] = f"{max_memory_used / 1024 / 1024:.3f}"

        if memory_size is not None:
            row["memory_size_mb"] = f"{memory_size / 1024 / 1024:.3f}"

        matched += 1

    print(f"Matched CloudWatch records: {matched}/{len(rows)}")

    fieldnames = list(rows[0].keys())

    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Saved enriched CSV: {csv_path}")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Enrich Experiment 3 CSVs with CloudWatch server-side metrics."
    )

    group = parser.add_mutually_exclusive_group(required=True)

    group.add_argument(
        "--csv",
        help="Single CSV file to enrich",
    )

    group.add_argument(
        "--dir",
        help="Directory containing Experiment 3 CSVs",
    )

    parser.add_argument(
        "--function",
        help="Lambda function name. Required with --csv.",
    )

    parser.add_argument(
        "--config",
        help="functions.json. Required with --dir.",
    )

    parser.add_argument(
        "--region",
        default="us-west-2",
        help="AWS region",
    )

    return parser.parse_args()


def main():
    args = parse_args()

    if args.csv:
        if not args.function:
            print("--function is required when using --csv")
            sys.exit(1)

        enrich_csv(
            csv_path=args.csv,
            function_name=args.function,
            region=args.region,
        )

        return

    if args.dir:
        if not args.config:
            print("--config is required when using --dir")
            sys.exit(1)

        with open(args.config) as f:
            functions = json.load(f)

        data_dir = Path(args.dir)

        for function_name in functions:
            matches = sorted(data_dir.glob(f"results_{function_name}_exp3.csv"))

            if not matches:
                print(f"No CSV found for {function_name} in {data_dir}")
                continue

            for csv_path in matches:
                enrich_csv(
                    csv_path=csv_path,
                    function_name=function_name,
                    region=args.region,
                )


if __name__ == "__main__":
    main()
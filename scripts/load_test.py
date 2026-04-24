#!/usr/bin/env python3
"""
Load testing script for AWS Lambda Function URLs.

Sustained profile: constant rate across all functions in config sequentially.
Burst profile    : idle 2 min → spike 500 req/s for 30s (single function only).

Usage:
    # Experiments 1 & 2 — sustained load across all functions
    python load_test.py --config scripts/experiment1/functions.json

    # Experiment 4 — burst profile (single function)
    python load_test.py --config scripts/experiment4/functions.json --profile burst

    # Single URL
    python load_test.py --url https://xxx.lambda-url.us-west-2.on.aws/ --label exp1-python-x86
"""

import argparse
import asyncio
import csv
import dataclasses
import json
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

import aiohttp


@dataclasses.dataclass
class RequestResult:
    request_id:         int
    profile:            str
    phase:              str
    timestamp_sent:     float
    timestamp_received: float
    latency_ms:         float
    http_status:        int
    lambda_request_id:  str
    error:              str


async def send_request(
    session: aiohttp.ClientSession,
    url: str,
    request_id: int,
    profile: str,
    phase: str,
    results: list,
) -> None:
    timestamp_sent = time.time()
    try:
        async with session.get(url) as response:
            await response.text()
            timestamp_received = time.time()
            results.append(RequestResult(
                request_id=request_id,
                profile=profile,
                phase=phase,
                timestamp_sent=timestamp_sent,
                timestamp_received=timestamp_received,
                latency_ms=(timestamp_received - timestamp_sent) * 1000,
                http_status=response.status,
                lambda_request_id=response.headers.get("x-amzn-requestid", ""),
                error="",
            ))
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        results.append(RequestResult(
            request_id=request_id,
            profile=profile,
            phase=phase,
            timestamp_sent=timestamp_sent,
            timestamp_received=time.time(),
            latency_ms=(time.time() - timestamp_sent) * 1000,
            http_status=0,
            lambda_request_id="",
            error=str(e),
        ))


async def fire_at_rate(session, url, rate, duration_secs, profile, phase, results, req_id_start=0):
    total = int(rate * duration_secs)
    loop = asyncio.get_event_loop()
    start = loop.time()
    tasks = []
    for i in range(total):
        scheduled = start + i / rate
        delay = scheduled - loop.time()
        if delay > 0:
            await asyncio.sleep(delay)
        tasks.append(asyncio.create_task(
            send_request(session, url, req_id_start + i, profile, phase, results)
        ))
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    return req_id_start + total


async def progress_reporter(label, results, total_requests, warmup_count, start_time, stop_event):
    while not stop_event.is_set():
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=10)
            break
        except asyncio.TimeoutError:
            pass
        elapsed = time.time() - start_time
        n = len(results)
        errors = sum(1 for r in results if r.error)
        phase = "warmup" if n < warmup_count else "measurement"
        print(f"  [{label}] [{elapsed:6.1f}s] {phase} | sent: {n}/{total_requests} | errors: {errors}")


async def run_sustained(url, label, rate, warmup_secs, duration_secs, req_timeout):
    results = []
    warmup_count = int(warmup_secs * rate)
    total_requests = int((warmup_secs + duration_secs) * rate)

    timeout = aiohttp.ClientTimeout(total=req_timeout)
    connector = aiohttp.TCPConnector(limit=0, ttl_dns_cache=300, enable_cleanup_closed=True)

    print(f"Profile: SUSTAINED | {total_requests} requests ({warmup_count} warmup + {total_requests - warmup_count} measurement)")
    print(f"Rate: {rate} req/s | Warmup: {warmup_secs}s | Duration: {duration_secs}s")
    print(f"URL: {url}")
    print()

    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        loop = asyncio.get_event_loop()
        start_time = loop.time()
        wall_start = time.time()

        stop_event = asyncio.Event()
        reporter = asyncio.create_task(
            progress_reporter(label, results, total_requests, warmup_count, wall_start, stop_event)
        )

        tasks = []
        for i in range(total_requests):
            scheduled = start_time + i / rate
            delay = scheduled - loop.time()
            if delay > 0:
                await asyncio.sleep(delay)
            phase = "warmup" if i < warmup_count else "measurement"
            tasks.append(asyncio.create_task(
                send_request(session, url, i, "sustained", phase, results)
            ))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        stop_event.set()
        await reporter

    return results


async def run_burst(url, req_timeout):
    results = []
    timeout = aiohttp.ClientTimeout(total=req_timeout)
    connector = aiohttp.TCPConnector(limit=0)

    print("Profile: BURST — idle 120s → 500 req/s for 30s")
    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        print("  [idle] waiting 120s...")
        await asyncio.sleep(120)
        print("  [spike] firing 500 req/s for 30s...")
        await fire_at_rate(session, url, 500, 30, "burst", "spike", results)
        print("  [spike] complete")

    return results


def write_csv(results, output_path):
    fields = [f.name for f in dataclasses.fields(RequestResult)]
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in sorted(results, key=lambda x: x.request_id):
            writer.writerow(dataclasses.asdict(r))
    print(f"Results written to {output_path}")


def print_summary(label, results, profile="sustained"):
    if profile == "burst":
        measurement = results
    else:
        measurement = [r for r in results if r.phase == "measurement"]

    if not measurement:
        print("No measurement data collected.")
        return

    successful = [r for r in measurement if r.http_status == 200]
    errors = [r for r in measurement if r.http_status != 200]

    print()
    print("=" * 60)
    print(f"SUMMARY: {label} ({profile.upper()})")
    print("=" * 60)
    print(f"Total requests : {len(measurement)}")
    print(f"Successful     : {len(successful)}")
    print(f"Errors         : {len(errors)}")
    if measurement:
        print(f"Error rate     : {len(errors) / len(measurement) * 100:.2f}%")

    if successful:
        timestamps = [r.timestamp_sent for r in successful]
        actual_duration = max(timestamps) - min(timestamps)
        if actual_duration > 0:
            print(f"Throughput     : {len(successful) / actual_duration:.2f} req/s")

        latencies = sorted(r.latency_ms for r in successful)
        print()
        print("Latency (ms):")
        print(f"  Min    : {min(latencies):.2f}")
        print(f"  Mean   : {statistics.mean(latencies):.2f}")
        print(f"  Median : {statistics.median(latencies):.2f}")
        if len(latencies) >= 100:
            q = statistics.quantiles(latencies, n=100)
            print(f"  P95    : {q[94]:.2f}")
            print(f"  P99    : {q[98]:.2f}")
        print(f"  Max    : {max(latencies):.2f}")
    print("=" * 60)


def parse_args():
    parser = argparse.ArgumentParser(description="Load test AWS Lambda Function URLs.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--url", help="Single Lambda Function URL")
    group.add_argument("--config", help="Path to JSON config file mapping labels to URLs")
    parser.add_argument("--profile", choices=["sustained", "burst"], default="sustained",
                        help="Load profile (default: sustained)")
    parser.add_argument("--rate", type=float, default=50, help="Requests per second (default: 50, sustained only)")
    parser.add_argument("--duration", type=float, default=300, help="Measurement duration in seconds (default: 300, sustained only)")
    parser.add_argument("--warmup", type=float, default=60, help="Warmup duration in seconds (default: 60, sustained only)")
    parser.add_argument("--timeout", type=float, default=30, help="Per-request timeout in seconds (default: 30)")
    parser.add_argument("--output-dir", type=str, default=None, help="Directory to save CSVs (default: data/experiment<N>/ derived from config path)")
    parser.add_argument("--output", type=str, default=None, help="CSV output path (single function only)")
    parser.add_argument("--label", type=str, default="lambda", help="Label for single URL mode")
    return parser.parse_args()


def resolve_output_dir(config_path: str) -> Path:
    parts = Path(config_path).parts
    for part in parts:
        if part.startswith("experiment"):
            output_dir = Path("data") / part
            output_dir.mkdir(parents=True, exist_ok=True)
            return output_dir
    output_dir = Path("data")
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def main():
    args = parse_args()

    try:
        if args.config:
            with open(args.config) as f:
                functions = json.load(f)

            output_dir = Path(args.output_dir) if args.output_dir else resolve_output_dir(args.config)

            if args.profile == "burst":
                if len(functions) != 1:
                    print("Error: burst profile requires exactly one function in config.")
                    sys.exit(1)
                label, url = next(iter(functions.items()))
                results = asyncio.run(run_burst(url, args.timeout))
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = Path(args.output) if args.output else output_dir / f"results_{label}_burst_{timestamp}.csv"
                write_csv(results, output_path)
                print_summary(label, results, "burst")
            else:
                total = len(functions)
                print(f"Loaded {total} functions from {args.config}")
                print()
                for i, (label, url) in enumerate(functions.items(), 1):
                    print(f"{'#' * 60}")
                    print(f"# [{i}/{total}] {label}")
                    print(f"{'#' * 60}")
                    results = asyncio.run(
                        run_sustained(url, label, args.rate, args.warmup, args.duration, args.timeout)
                    )
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    output_path = output_dir / f"results_{label}_{timestamp}.csv"
                    write_csv(results, output_path)
                    print_summary(label, results)
                    print()
                print(f"All {total} functions tested.")
        else:
            if args.profile == "burst":
                results = asyncio.run(run_burst(args.url, args.timeout))
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = Path(args.output or f"results_{args.label}_burst_{timestamp}.csv")
            else:
                results = asyncio.run(
                    run_sustained(args.url, args.label, args.rate, args.warmup, args.duration, args.timeout)
                )
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = Path(args.output or f"results_{args.label}_{timestamp}.csv")
            write_csv(results, output_path)
            print_summary(args.label, results, args.profile)

    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(1)


if __name__ == "__main__":
    main()

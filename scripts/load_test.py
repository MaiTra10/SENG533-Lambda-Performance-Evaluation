#!/usr/bin/env python3
"""
Load testing script for AWS Lambda Function URLs.

Sends sustained HTTP GET requests at a configurable rate and records
per-request latency metrics to CSV for post-processing.

Usage (single function):
    python load_test.py --url https://xxxxx.lambda-url.us-west-2.on.aws/ --label exp1-python-x86

Usage (all functions from config):
    python load_test.py --config functions.json
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
    request_id: int
    phase: str
    timestamp_sent: float
    timestamp_received: float
    latency_ms: float
    http_status: int
    response_body: str
    error: str


async def send_request(
    session: aiohttp.ClientSession,
    url: str,
    request_id: int,
    phase: str,
    results: list[RequestResult],
) -> None:
    timestamp_sent = time.time()
    try:
        async with session.get(url) as response:
            body = await response.text()
            timestamp_received = time.time()
            results.append(RequestResult(
                request_id=request_id,
                phase=phase,
                timestamp_sent=timestamp_sent,
                timestamp_received=timestamp_received,
                latency_ms=(timestamp_received - timestamp_sent) * 1000,
                http_status=response.status,
                response_body=body[:1024],
                error="",
            ))
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        timestamp_received = time.time()
        results.append(RequestResult(
            request_id=request_id,
            phase=phase,
            timestamp_sent=timestamp_sent,
            timestamp_received=timestamp_received,
            latency_ms=(timestamp_received - timestamp_sent) * 1000,
            http_status=0,
            response_body="",
            error=str(e),
        ))


async def progress_reporter(
    label: str,
    results: list[RequestResult],
    total_requests: int,
    warmup_count: int,
    start_time: float,
    stop_event: asyncio.Event,
) -> None:
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


async def run_load_test(
    url: str,
    label: str,
    rate: float,
    warmup_secs: float,
    duration_secs: float,
    req_timeout: float,
) -> list[RequestResult]:
    results: list[RequestResult] = []
    warmup_count = int(warmup_secs * rate)
    total_requests = int((warmup_secs + duration_secs) * rate)

    timeout = aiohttp.ClientTimeout(total=req_timeout)
    connector = aiohttp.TCPConnector(limit=0, ttl_dns_cache=300, enable_cleanup_closed=True)

    print(f"Starting load test: {total_requests} total requests ({warmup_count} warmup + {total_requests - warmup_count} measurement)")
    print(f"Target rate: {rate} req/s | Warmup: {warmup_secs}s | Measurement: {duration_secs}s")
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

        tasks: list[asyncio.Task] = []
        for i in range(total_requests):
            scheduled = start_time + i / rate
            delay = scheduled - loop.time()
            if delay > 0:
                await asyncio.sleep(delay)

            phase = "warmup" if i < warmup_count else "measurement"
            tasks.append(asyncio.create_task(
                send_request(session, url, i, phase, results)
            ))

        # Wait for all outstanding requests to complete
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        stop_event.set()
        await reporter

    return results


def write_csv(results: list[RequestResult], output_path: Path) -> None:
    fields = [f.name for f in dataclasses.fields(RequestResult)]
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in sorted(results, key=lambda x: x.request_id):
            writer.writerow(dataclasses.asdict(r))
    print(f"Results written to {output_path}")


def print_summary(label: str, results: list[RequestResult]) -> None:
    measurement = [r for r in results if r.phase == "measurement"]
    if not measurement:
        print("No measurement data collected.")
        return

    successful = [r for r in measurement if r.http_status == 200]
    errors = [r for r in measurement if r.http_status != 200]

    print()
    print("=" * 60)
    print(f"SUMMARY: {label} (measurement phase only)")
    print("=" * 60)
    print(f"Total requests:    {len(measurement)}")
    print(f"Successful:        {len(successful)}")
    print(f"Errors:            {len(errors)}")
    print(f"Error rate:        {len(errors) / len(measurement) * 100:.2f}%")

    if successful:
        timestamps = [r.timestamp_sent for r in measurement]
        actual_duration = max(timestamps) - min(timestamps)
        if actual_duration > 0:
            print(f"Actual throughput: {len(successful) / actual_duration:.2f} req/s")

        latencies = [r.latency_ms for r in successful]
        latencies.sort()
        print()
        print("Latency (ms):")
        print(f"  Min:    {min(latencies):.2f}")
        print(f"  Mean:   {statistics.mean(latencies):.2f}")
        print(f"  Median: {statistics.median(latencies):.2f}")
        if len(latencies) >= 100:
            quantiles = statistics.quantiles(latencies, n=100)
            print(f"  P95:    {quantiles[94]:.2f}")
            print(f"  P99:    {quantiles[98]:.2f}")
        print(f"  Max:    {max(latencies):.2f}")
    print("=" * 60)


def run_single(args: argparse.Namespace) -> None:
    label = args.label or "lambda"
    if args.output:
        output_path = Path(args.output)
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = Path(f"results_{label}_{timestamp}.csv")

    results = asyncio.run(
        run_load_test(args.url, label, args.rate, args.warmup, args.duration, args.timeout)
    )
    write_csv(results, output_path)
    print_summary(label, results)


def run_all_from_config(args: argparse.Namespace) -> None:
    config_path = Path(args.config)
    with open(config_path) as f:
        functions = json.load(f)

    total = len(functions)
    print(f"Loaded {total} functions from {config_path}")
    print()

    for i, (label, url) in enumerate(functions.items(), 1):
        print(f"{'#' * 60}")
        print(f"# [{i}/{total}] {label}")
        print(f"{'#' * 60}")

        results = asyncio.run(
            run_load_test(url, label, args.rate, args.warmup, args.duration, args.timeout)
        )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = Path(f"results_{label}_{timestamp}.csv")
        write_csv(results, output_path)
        print_summary(label, results)
        print()

    print(f"All {total} functions tested.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Load test AWS Lambda Function URLs at a sustained request rate."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--url", help="Lambda Function URL to test (single function mode)")
    group.add_argument("--config", help="Path to JSON config file mapping labels to URLs (multi-function mode)")
    parser.add_argument("--rate", type=float, default=50, help="Requests per second (default: 50)")
    parser.add_argument("--duration", type=float, default=300, help="Measurement phase duration in seconds (default: 300)")
    parser.add_argument("--warmup", type=float, default=60, help="Warm-up duration in seconds (default: 60)")
    parser.add_argument("--timeout", type=float, default=15, help="Per-request HTTP timeout in seconds (default: 15)")
    parser.add_argument("--output", type=str, default=None, help="CSV output file path (single function mode only)")
    parser.add_argument("--label", type=str, default="", help="Run label (single function mode only)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    try:
        if args.config:
            run_all_from_config(args)
        else:
            run_single(args)
    except KeyboardInterrupt:
        print("\nInterrupted!")
        sys.exit(1)


if __name__ == "__main__":
    main()

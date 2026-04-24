#!/usr/bin/env python3

"""
Experiment 3: Cold vs Warm Start Behavior for AWS Lambda.

This script is designed for:
  - exp3-python-x86
  - exp3-go-x86
  - exp3-java-x86

Metrics collected client-side:
  - end-to-end latency
  - HTTP status
  - Lambda request ID
  - error flag
  - timeout flag
  - throughput inputs

Cold test:
  - wait N seconds
  - invoke all functions once in parallel
  - repeat for cold sample count

Warm test:
  - prewarm each function
  - send exactly N observations per function at a fixed rate
"""

import argparse
import asyncio
import csv
import dataclasses
import json
import statistics
import sys
import time
from pathlib import Path

import aiohttp


@dataclasses.dataclass
class RequestResult:
    request_id: int
    function_label: str
    runtime: str
    profile: str
    phase: str
    timestamp_sent: float
    timestamp_received: float
    latency_ms: float
    http_status: int
    lambda_request_id: str
    error: str
    is_timeout: bool


def infer_runtime(label: str) -> str:
    label = label.lower()

    if "python" in label:
        return "python"

    if "java" in label:
        return "java"

    if "go" in label:
        return "go"

    return "unknown"


async def send_request(
    session: aiohttp.ClientSession,
    url: str,
    request_id: int,
    function_label: str,
    profile: str,
    phase: str,
    results: list[RequestResult],
) -> None:
    timestamp_sent = time.time()

    try:
        async with session.get(url) as response:
            await response.text()
            timestamp_received = time.time()

            results.append(
                RequestResult(
                    request_id=request_id,
                    function_label=function_label,
                    runtime=infer_runtime(function_label),
                    profile=profile,
                    phase=phase,
                    timestamp_sent=timestamp_sent,
                    timestamp_received=timestamp_received,
                    latency_ms=(timestamp_received - timestamp_sent) * 1000,
                    http_status=response.status,
                    lambda_request_id=response.headers.get("x-amzn-requestid", ""),
                    error="",
                    is_timeout=False,
                )
            )

    except asyncio.TimeoutError as e:
        timestamp_received = time.time()

        results.append(
            RequestResult(
                request_id=request_id,
                function_label=function_label,
                runtime=infer_runtime(function_label),
                profile=profile,
                phase=phase,
                timestamp_sent=timestamp_sent,
                timestamp_received=timestamp_received,
                latency_ms=(timestamp_received - timestamp_sent) * 1000,
                http_status=0,
                lambda_request_id="",
                error=str(e),
                is_timeout=True,
            )
        )

    except aiohttp.ClientError as e:
        timestamp_received = time.time()

        results.append(
            RequestResult(
                request_id=request_id,
                function_label=function_label,
                runtime=infer_runtime(function_label),
                profile=profile,
                phase=phase,
                timestamp_sent=timestamp_sent,
                timestamp_received=timestamp_received,
                latency_ms=(timestamp_received - timestamp_sent) * 1000,
                http_status=0,
                lambda_request_id="",
                error=str(e),
                is_timeout=False,
            )
        )


async def run_cold_round(
    functions: dict[str, str],
    round_number: int,
    timeout_seconds: float,
) -> list[RequestResult]:
    results: list[RequestResult] = []

    timeout = aiohttp.ClientTimeout(total=timeout_seconds)
    connector = aiohttp.TCPConnector(
        limit=0,
        ttl_dns_cache=300,
        enable_cleanup_closed=True,
    )

    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        tasks = []

        for label, url in functions.items():
            tasks.append(
                asyncio.create_task(
                    send_request(
                        session=session,
                        url=url,
                        request_id=round_number,
                        function_label=label,
                        profile="cold_vs_warm",
                        phase="cold",
                        results=results,
                    )
                )
            )

        await asyncio.gather(*tasks, return_exceptions=True)

    return results


async def run_cold_test(
    functions: dict[str, str],
    cold_samples: int,
    idle_seconds: int,
    timeout_seconds: float,
) -> dict[str, list[RequestResult]]:
    all_results = {label: [] for label in functions}

    print()
    print("=" * 90)
    print("EXPERIMENT 3 COLD TEST")
    print("=" * 90)
    print(f"Functions     : {', '.join(functions.keys())}")
    print(f"Cold samples  : {cold_samples} per function")
    print(f"Idle gap      : {idle_seconds} seconds before each cold round")
    print(f"Estimated time: {(cold_samples * idle_seconds) / 60:.1f} minutes plus request overhead")
    print("=" * 90)

    for round_number in range(cold_samples):
        print()
        print(f"[cold] Round {round_number + 1}/{cold_samples}")
        print(f"[cold] Waiting {idle_seconds} seconds to encourage cold starts...")

        await asyncio.sleep(idle_seconds)

        print("[cold] Invoking all functions once in parallel...")
        round_results = await run_cold_round(
            functions=functions,
            round_number=round_number,
            timeout_seconds=timeout_seconds,
        )

        for result in round_results:
            all_results[result.function_label].append(result)

            print(
                f"  {result.function_label:18s} "
                f"status={result.http_status:<3} "
                f"latency={result.latency_ms:9.2f} ms "
                f"timeout={str(result.is_timeout):5s} "
                f"request_id={result.lambda_request_id}"
            )

    return all_results


async def prewarm_function(
    label: str,
    url: str,
    prewarm_count: int,
    timeout_seconds: float,
) -> None:
    timeout = aiohttp.ClientTimeout(total=timeout_seconds)
    connector = aiohttp.TCPConnector(
        limit=0,
        ttl_dns_cache=300,
        enable_cleanup_closed=True,
    )

    temp_results: list[RequestResult] = []

    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        for i in range(prewarm_count):
            await send_request(
                session=session,
                url=url,
                request_id=-(i + 1),
                function_label=label,
                profile="cold_vs_warm",
                phase="prewarm",
                results=temp_results,
            )

    success_count = sum(1 for r in temp_results if r.http_status == 200 and not r.error)
    print(f"[warm] Prewarmed {label}: {success_count}/{prewarm_count} successful")


async def run_warm_function(
    label: str,
    url: str,
    observations: int,
    rate: float,
    timeout_seconds: float,
    prewarm_count: int,
) -> list[RequestResult]:
    results: list[RequestResult] = []

    print()
    print("=" * 90)
    print(f"WARM TEST: {label}")
    print("=" * 90)
    print(f"Observations : {observations}")
    print(f"Rate         : {rate} req/s")
    print(f"Expected time: {observations / rate:.1f} seconds")
    print(f"Prewarm count: {prewarm_count}")
    print("=" * 90)

    await prewarm_function(
        label=label,
        url=url,
        prewarm_count=prewarm_count,
        timeout_seconds=timeout_seconds,
    )

    timeout = aiohttp.ClientTimeout(total=timeout_seconds)
    connector = aiohttp.TCPConnector(
        limit=0,
        ttl_dns_cache=300,
        enable_cleanup_closed=True,
    )

    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        loop = asyncio.get_event_loop()
        start = loop.time()

        tasks = []

        for i in range(observations):
            scheduled = start + i / rate
            delay = scheduled - loop.time()

            if delay > 0:
                await asyncio.sleep(delay)

            tasks.append(
                asyncio.create_task(
                    send_request(
                        session=session,
                        url=url,
                        request_id=i,
                        function_label=label,
                        profile="cold_vs_warm",
                        phase="warm",
                        results=results,
                    )
                )
            )

            if (i + 1) % 500 == 0:
                print(f"[warm] {label}: scheduled {i + 1}/{observations}")

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    return results


async def run_warm_test(
    functions: dict[str, str],
    observations: int,
    rate: float,
    timeout_seconds: float,
    prewarm_count: int,
    parallel: bool,
) -> dict[str, list[RequestResult]]:
    print()
    print("=" * 90)
    print("EXPERIMENT 3 WARM TEST")
    print("=" * 90)
    print(f"Functions       : {', '.join(functions.keys())}")
    print(f"Observations    : {observations} per function")
    print(f"Rate            : {rate} req/s per function")
    print(f"Parallel warm   : {parallel}")
    print("=" * 90)

    if parallel:
        tasks = [
            asyncio.create_task(
                run_warm_function(
                    label=label,
                    url=url,
                    observations=observations,
                    rate=rate,
                    timeout_seconds=timeout_seconds,
                    prewarm_count=prewarm_count,
                )
            )
            for label, url in functions.items()
        ]

        task_results = await asyncio.gather(*tasks)

        return {
            label: results
            for label, results in zip(functions.keys(), task_results)
        }

    all_results = {}

    for label, url in functions.items():
        all_results[label] = await run_warm_function(
            label=label,
            url=url,
            observations=observations,
            rate=rate,
            timeout_seconds=timeout_seconds,
            prewarm_count=prewarm_count,
        )

    return all_results


def write_csv(results: list[RequestResult], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fields = [field.name for field in dataclasses.fields(RequestResult)]

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()

        for row in sorted(results, key=lambda r: (r.phase, r.request_id)):
            writer.writerow(dataclasses.asdict(row))

    print(f"Saved: {output_path}")


def print_summary(label: str, results: list[RequestResult]) -> None:
    print()
    print("-" * 90)
    print(f"SUMMARY: {label}")
    print("-" * 90)

    for phase in ["cold", "warm"]:
        phase_results = [r for r in results if r.phase == phase]

        if not phase_results:
            continue

        successful = [
            r for r in phase_results
            if r.http_status == 200 and not r.error
        ]

        failed = [
            r for r in phase_results
            if r.http_status != 200 or r.error
        ]

        timed_out = [r for r in phase_results if r.is_timeout]

        print()
        print(f"Phase: {phase}")
        print(f"  Total requests : {len(phase_results)}")
        print(f"  Successful     : {len(successful)}")
        print(f"  Errors         : {len(failed)}")
        print(f"  Timeouts       : {len(timed_out)}")
        print(f"  Error rate     : {(len(failed) / len(phase_results)) * 100:.2f}%")
        print(f"  Timeout rate   : {(len(timed_out) / len(phase_results)) * 100:.2f}%")

        if successful:
            timestamps = [r.timestamp_sent for r in successful]

            if len(timestamps) >= 2:
                duration = max(timestamps) - min(timestamps)

                if duration > 0:
                    print(f"  Throughput     : {len(successful) / duration:.2f} req/s")

            latencies = sorted(r.latency_ms for r in successful)

            print("  End-to-end latency:")
            print(f"    Min    : {min(latencies):.2f} ms")
            print(f"    Mean   : {statistics.mean(latencies):.2f} ms")
            print(f"    Median : {statistics.median(latencies):.2f} ms")

            if len(latencies) >= 100:
                q = statistics.quantiles(latencies, n=100)
                print(f"    P95    : {q[94]:.2f} ms")
                print(f"    P99    : {q[98]:.2f} ms")

            print(f"    Max    : {max(latencies):.2f} ms")

    print("-" * 90)


def merge_result_maps(
    existing: dict[str, list[RequestResult]],
    new: dict[str, list[RequestResult]],
) -> dict[str, list[RequestResult]]:
    merged = {label: list(rows) for label, rows in existing.items()}

    for label, rows in new.items():
        merged.setdefault(label, [])
        merged[label].extend(rows)

    return merged


def parse_args():
    parser = argparse.ArgumentParser(
        description="Experiment 3 cold vs warm load test for AWS Lambda Function URLs."
    )

    parser.add_argument(
        "--config",
        required=True,
        help="Path to scripts/experiment3/functions.json",
    )

    parser.add_argument(
        "--output-dir",
        default="data/experiment3",
        help="Directory for output CSVs",
    )

    parser.add_argument(
        "--mode",
        choices=["cold", "warm", "both"],
        default="both",
        help="Run cold test, warm test, or both",
    )

    parser.add_argument(
        "--cold-samples",
        type=int,
        default=5,
        help="Cold observations per function",
    )

    parser.add_argument(
        "--idle-seconds",
        type=int,
        default=900,
        help="Idle time before each cold round. Default 900 seconds = 15 minutes.",
    )

    parser.add_argument(
        "--warm-observations",
        type=int,
        default=5000,
        help="Warm observations per function",
    )

    parser.add_argument(
        "--rate",
        type=float,
        default=50,
        help="Warm request rate per function",
    )

    parser.add_argument(
        "--prewarm-count",
        type=int,
        default=5,
        help="Prewarm requests before warm measurement",
    )

    parser.add_argument(
        "--timeout",
        type=float,
        default=30,
        help="Client request timeout in seconds",
    )

    parser.add_argument(
        "--parallel-warm",
        action="store_true",
        help="Run warm tests for all functions in parallel. Faster but less isolated.",
    )

    return parser.parse_args()


def main():
    args = parse_args()

    with open(args.config) as f:
        functions = json.load(f)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print()
    print("=" * 90)
    print("EXPERIMENT 3 CONFIG")
    print("=" * 90)
    print(f"Config file       : {args.config}")
    print(f"Output directory  : {output_dir}")
    print(f"Mode              : {args.mode}")
    print(f"Functions         : {', '.join(functions.keys())}")
    print(f"Cold samples      : {args.cold_samples} per function")
    print(f"Idle seconds      : {args.idle_seconds}")
    print(f"Warm observations : {args.warm_observations} per function")
    print(f"Warm rate         : {args.rate} req/s per function")
    print(f"Parallel warm     : {args.parallel_warm}")

    cold_minutes = (args.cold_samples * args.idle_seconds) / 60 if args.mode in ["cold", "both"] else 0

    if args.mode in ["warm", "both"]:
        if args.parallel_warm:
            warm_minutes = (args.warm_observations / args.rate) / 60
        else:
            warm_minutes = (len(functions) * args.warm_observations / args.rate) / 60
    else:
        warm_minutes = 0

    print()
    print(f"Estimated cold time: {cold_minutes:.1f} minutes")
    print(f"Estimated warm time: {warm_minutes:.1f} minutes")
    print(f"Estimated total    : {cold_minutes + warm_minutes:.1f} minutes plus overhead")
    print("=" * 90)

    try:
        all_results = {label: [] for label in functions}

        if args.mode in ["cold", "both"]:
            cold_results = asyncio.run(
                run_cold_test(
                    functions=functions,
                    cold_samples=args.cold_samples,
                    idle_seconds=args.idle_seconds,
                    timeout_seconds=args.timeout,
                )
            )

            all_results = merge_result_maps(all_results, cold_results)

        if args.mode in ["warm", "both"]:
            warm_results = asyncio.run(
                run_warm_test(
                    functions=functions,
                    observations=args.warm_observations,
                    rate=args.rate,
                    timeout_seconds=args.timeout,
                    prewarm_count=args.prewarm_count,
                    parallel=args.parallel_warm,
                )
            )

            all_results = merge_result_maps(all_results, warm_results)

        for label, results in all_results.items():
            output_path = output_dir / f"results_{label}_exp3.csv"
            write_csv(results, output_path)
            print_summary(label, results)

    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(1)


if __name__ == "__main__":
    main()
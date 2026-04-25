#!/usr/bin/env python3

import argparse
import asyncio
import csv
import dataclasses
import json
import statistics
import sys
import time
import random
import ssl
from pathlib import Path

import aiohttp
import certifi


@dataclasses.dataclass
class RequestResult:
    request_id: int
    function_label: str
    phase: str
    timestamp_sent: float
    timestamp_received: float
    latency_ms: float
    http_status: int
    lambda_request_id: str
    error: str
    response_snippet: str


async def send_request(
    session,
    url,
    request_id,
    label,
    phase,
    results,
    print_errors=True,
    max_retries=2
):
    timestamp_sent = time.time()

    for attempt in range(max_retries + 1):
        try:
            async with session.get(url) as response:
                body = await response.text()
                timestamp_received = time.time()

                if response.status == 429 and attempt < max_retries:
                    wait = (2 ** attempt) + random.uniform(0, 1)
                    await asyncio.sleep(wait)
                    continue

                if response.status != 200 and print_errors:
                    print("\n--- ERROR RESPONSE ---")
                    print(f"[{label}] status={response.status}")
                    print(body[:500])
                    print("----------------------\n")

                results.append(RequestResult(
                    request_id=request_id,
                    function_label=label,
                    phase=phase,
                    timestamp_sent=timestamp_sent,
                    timestamp_received=timestamp_received,
                    latency_ms=(timestamp_received - timestamp_sent) * 1000,
                    http_status=response.status,
                    lambda_request_id=response.headers.get("x-amzn-requestid", ""),
                    error="" if response.status == 200 else f"HTTP {response.status}",
                    response_snippet=body[:200]
                ))
                return

        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            if attempt < max_retries:
                wait = (2 ** attempt) + random.uniform(0, 1)
                await asyncio.sleep(wait)
                continue

            if print_errors:
                print("\n--- CLIENT ERROR ---")
                print(f"[{label}] {str(e)}")
                print("--------------------\n")

            results.append(RequestResult(
                request_id=request_id,
                function_label=label,
                phase=phase,
                timestamp_sent=timestamp_sent,
                timestamp_received=time.time(),
                latency_ms=(time.time() - timestamp_sent) * 1000,
                http_status=0,
                lambda_request_id="",
                error=str(e),
                response_snippet=""
            ))
            return


async def progress_reporter(label, results, total_requests, start_time, stop_event):
    while not stop_event.is_set():
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=5)
            break
        except asyncio.TimeoutError:
            pass

        elapsed = time.time() - start_time
        completed = len(results)
        errors = sum(1 for r in results if r.http_status != 200)

        print(f"[{label}] {elapsed:6.1f}s | completed: {completed}/{total_requests} | errors: {errors}")


async def fire_at_rate(session, url, label, rate, duration, results, warmup_count):
    total = int(rate * duration)
    loop = asyncio.get_event_loop()
    start = loop.time()

    tasks = []

    for i in range(total):
        scheduled = start + i / rate
        delay = scheduled - loop.time()
        if delay > 0:
            await asyncio.sleep(delay)

        phase = "warmup" if i < warmup_count else "measurement"

        tasks.append(asyncio.create_task(
            send_request(session, url, i, label, phase, results)
        ))

    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


async def run_single(url, label, rate, warmup, duration, timeout_sec, concurrency):
    results = []

    total_duration = warmup + duration
    total_requests = int(rate * total_duration)
    warmup_count = int(rate * warmup)

    timeout = aiohttp.ClientTimeout(total=timeout_sec)

    ssl_context = ssl.create_default_context(cafile=certifi.where())

    connector = aiohttp.TCPConnector(
        limit=concurrency,
        ssl=ssl_context
    )

    print("\n" + "=" * 60)
    print(f"Testing: {label}")
    print(f"Rate={rate} req/s | Concurrency={concurrency}")
    print("=" * 60 + "\n")

    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        stop_event = asyncio.Event()
        start_time = time.time()

        reporter = asyncio.create_task(
            progress_reporter(label, results, total_requests, start_time, stop_event)
        )

        await fire_at_rate(session, url, label, rate, total_duration, results, warmup_count)

        stop_event.set()
        await reporter

    return results


def write_csv(results, path):
    fields = [f.name for f in dataclasses.fields(RequestResult)]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in results:
            writer.writerow(dataclasses.asdict(r))


def print_summary(label, results):
    measurement = [r for r in results if r.phase == "measurement"]

    if not measurement:
        print("No measurement data")
        return

    success = [r for r in measurement if r.http_status == 200]
    errors = [r for r in measurement if r.http_status != 200]

    print("\n" + "=" * 50)
    print(f"{label}")
    print("=" * 50)
    print(f"Total: {len(measurement)}")
    print(f"Success: {len(success)}")
    print(f"Errors: {len(errors)}")
    print(f"Error rate: {len(errors)/len(measurement)*100:.2f}%")

    if success:
        lat = sorted(r.latency_ms for r in success)
        print(f"Mean: {statistics.mean(lat):.2f} ms")
        print(f"P95: {lat[int(len(lat)*0.95)]:.2f} ms")
        print(f"P99: {lat[int(len(lat)*0.99)]:.2f} ms")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--rate", type=float, default=5)
    parser.add_argument("--duration", type=float, default=60)
    parser.add_argument("--warmup", type=float, default=10)
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--output-dir", default="data")

    args = parser.parse_args()

    with open(args.config) as f:
        functions = json.load(f)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nLoaded {len(functions)} functions")
    print("Running ONE BY ONE (sequential debugging mode)\n")

    for label, url in functions.items():
        results = asyncio.run(
            run_single(
                url,
                label,
                args.rate,
                args.warmup,
                args.duration,
                args.timeout,
                args.concurrency
            )
        )

        path = output_dir / f"{label}_debug.csv"
        write_csv(results, path)

        print_summary(label, results)

    print("\nAll functions tested.")


if __name__ == "__main__":
    main()
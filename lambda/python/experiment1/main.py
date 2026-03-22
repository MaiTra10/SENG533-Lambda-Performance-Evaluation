import json
import resource
import time
from matrixMultiplication import multiply_matrix
from s3Upload import upload_file


def _rss_mb():
    # ru_maxrss is in KB on Linux
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def exp1_workloads(event, context):
    mem_before_cpu = _rss_mb()
    t0 = time.perf_counter()
    multiply_matrix()
    cpu_ms = (time.perf_counter() - t0) * 1000
    mem_after_cpu = _rss_mb()

    mem_before_io = _rss_mb()
    t1 = time.perf_counter()
    upload_file()
    io_ms = (time.perf_counter() - t1) * 1000
    mem_after_io = _rss_mb()

    print(json.dumps({
        "_aws": {
            "Timestamp": int(time.time() * 1000),
            "CloudWatchMetrics": [{
                "Namespace": "SENG533/Experiment1",
                "Dimensions": [["FunctionName"]],
                "Metrics": [
                    {"Name": "CpuDuration",    "Unit": "Milliseconds"},
                    {"Name": "IoDuration",     "Unit": "Milliseconds"},
                    {"Name": "CpuMemoryMB",    "Unit": "Megabytes"},
                    {"Name": "IoMemoryMB",     "Unit": "Megabytes"},
                    {"Name": "TotalMemoryMB",  "Unit": "Megabytes"},
                ]
            }]
        },
        "FunctionName":   context.function_name,
        "CpuDuration":    cpu_ms,
        "IoDuration":     io_ms,
        "CpuMemoryMB":    mem_after_cpu - mem_before_cpu,
        "IoMemoryMB":     mem_after_io  - mem_before_io,
        "TotalMemoryMB":  mem_after_io,
    }))

    return {"statusCode": 200, "body": "ok"}
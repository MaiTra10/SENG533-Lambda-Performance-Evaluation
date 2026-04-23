# SENG533 - Lambda Performance Evaluation

Repository to store code for evaluating AWS Lambda functions based on allocated memory, runtime and processor architecture.

---

## Prerequisites

- Python 3.9+
- AWS CLI configured (`aws configure`)
- Terraform
- Go (for building Go Lambda binaries)
- Java JDK (for building Java Lambda JARs)

Install Python dependencies:

```bash
pip3 install aiohttp boto3 matplotlib
```

---

## Project Structure

```
lambda/
  python/experiment1/     # Python CPU + I/O workload
  go/experiment1/         # Go CPU workload
  java/experiment1/       # Java CPU workload (also used by Experiment 2)
scripts/
  load_test.py            # Unified load testing script (all experiments)
  analyze.py              # CloudWatch log analysis + box plots
  experiment1/
    functions.json        # Experiment 1 function URLs
  experiment2/
    functions.json        # Experiment 2 function URLs
  experiment4/
    functions.json        # Experiment 4 function URL
infra/
  main.tf                 # Terraform — all Lambda infrastructure
```

---

## Deployment

### 1. Build Artifacts

**Python (Experiment 1):**

```bash
cd lambda/python/experiment1
mkdir -p deploy
zip deploy/bootstrap.zip main.py matrixMultiplication.py s3Upload.py
```

**Go (Experiment 1 — build separately per architecture):**

```bash
cd lambda/go
mkdir -p experiment1/deploy

GOOS=linux GOARCH=amd64 go build -o experiment1/deploy/bootstrap ./experiment1/matrixMultiplication.go
cd experiment1/deploy && zip bootstrap-x86.zip bootstrap && rm bootstrap && cd ../../..

GOOS=linux GOARCH=arm64 go build -o experiment1/deploy/bootstrap ./experiment1/matrixMultiplication.go
cd experiment1/deploy && zip bootstrap-arm.zip bootstrap && rm bootstrap && cd ../../..
```

**Java (Experiment 1 + 2 — same JAR):**

```bash
cd lambda/java/experiment1
mkdir -p deploy out
javac -cp lib/aws-lambda-java-core-1.4.0.jar -d out Handler.java
jar cf deploy/bootstrap.jar -C out .
mkdir -p /tmp/lambda-deps && cd /tmp/lambda-deps
jar xf /path/to/lambda/java/experiment1/lib/aws-lambda-java-core-1.4.0.jar
jar uf /path/to/lambda/java/experiment1/deploy/bootstrap.jar -C /tmp/lambda-deps .
```

### 2. Deploy with Terraform

```bash
cd infra
terraform init
terraform apply
```

After a successful apply, Function URLs are written to `infra/details/lambda_function_urls.json`. Copy the URLs into the relevant `functions.json` files under `scripts/`.

---

## Running the Experiments

### Experiment 1 — Runtime Environment Impact

Tests Python, Go, and Java across x86 and ARM at 1769 MB. Sustained 50 req/s for 5 minutes with a 60s warmup.

```bash
python3 scripts/load_test.py --config scripts/experiment1/functions.json
```

### Experiment 2 — Memory Allocation & Cost Efficiency

Tests Java across 4 memory configs (128, 1024, 1769, 3008 MB) on x86 and ARM. Same sustained profile.

```bash
python3 scripts/load_test.py --config scripts/experiment2/functions.json
```

### Experiment 4 — Burst vs Sustained

Tests Python x86 at 1769 MB under two traffic profiles. Run both back to back.

**Sustained** (50 req/s for 5 minutes):

```bash
python3 scripts/load_test.py --config scripts/experiment4/functions.json --profile sustained
```

**Burst** (idle 2 min → 500 req/s for 30s):

```bash
python3 scripts/load_test.py --config scripts/experiment4/functions.json --profile burst
```

Each run saves a CSV file to `data/experiment{N}/results_{label}_{timestamp}.csv` automatically based on the config path. Override with `--output-dir`.

---

## Generating Plots

After running a load test, wait 1-2 minutes for CloudWatch to ingest logs, then run:

```bash
# Experiment 1
python3 scripts/analyze.py --config scripts/experiment1/functions.json --region us-west-2 --start 1h --output-dir plots/experiment1

# Experiment 2
python3 scripts/analyze.py --config scripts/experiment2/functions.json --region us-west-2 --start 1h --output-dir plots/experiment2
```

This queries CloudWatch Logs Insights and saves 3 box plots per experiment:

- `execution_duration.png` — Lambda execution time (ms)
- `memory_used.png` — Peak memory used (MB)
- `cost_per_invocation.png` — Estimated cost per invocation (USD)

After both runs complete, generate plots from the CSVs:

```bash
python3 scripts/experiment4/analyze.py \
    --sustained data/experiment4/results_exp4-python-x86-sustained_<ts>.csv \
    --burst     data/experiment4/results_exp4-python-x86-burst_<ts>.csv \
    --output-dir plots/experiment4
```

The script auto-discovers the latest CSVs in `data/experiment4/` if `--sustained`/`--burst` are omitted.

Plots generated:

- `latency_boxplot.png` — end-to-end latency distribution (burst vs sustained)
- `latency_cdf.png` — latency CDF comparison
- `throughput.png` — requests/s over time for each profile
- `error_timeout_rate.png` — error rate & timeout rate side-by-side

To also plot Lambda execution duration from CloudWatch:

```bash
python3 scripts/experiment4/analyze.py \
    --function exp4-python-x86 \
    --region us-west-2 \
    --start 2h
```

---

## Load Test Options

| Flag | Default | Description |
| --- | --- | --- |
| `--config` | — | Path to `functions.json` |
| `--profile` | `sustained` | `sustained` or `burst` |
| `--rate` | `50` | Requests per second (sustained only) |
| `--duration` | `300` | Measurement duration in seconds (sustained only) |
| `--warmup` | `60` | Warmup duration in seconds (sustained only) |
| `--timeout` | `30` | Per-request HTTP timeout in seconds |
| `--output-dir` | `data/experiment{N}/` | Directory to save CSVs (derived from config path) |
| `--url` | — | Single function URL (instead of config file) |
| `--label` | `lambda` | Label for single URL mode |

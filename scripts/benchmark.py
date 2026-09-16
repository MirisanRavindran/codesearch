"""Latency benchmark. Runs 25 varied queries 5 times each against a warm API."""
import httpx
import statistics
import time

QUERIES = [
    "parse json from http response",
    "retry decorator with exponential backoff",
    "sort a list of dictionaries by key",
    "read a large file line by line",
    "make an authenticated http request",
    "compute hash of a string",
    "connect to postgres database",
    "serialize object to yaml",
    "download file from url",
    "run shell command and capture output",
    "encode url query parameters",
    "convert datetime to iso string",
    "batch iterate over a large sequence",
    "async context manager",
    "cli argument parser",
    "log rotation configuration",
    "flatten nested dictionary",
    "check if file exists",
    "compress bytes with gzip",
    "aes encrypt string",
    "regex match email address",
    "walk directory tree recursively",
    "read csv file into dataframe",
    "http client with timeout",
    "generate random string",
]

def main():
    latencies = []
    with httpx.Client(base_url="http://localhost:8000", timeout=60.0) as c:
        print("warming up…")
        c.post("/search", json={"query": "warmup", "top_k": 10})

        print(f"Running {len(QUERIES)} queries x 5 = {len(QUERIES)*5} total requests…")
        for run in range(5):
            for q in QUERIES:
                t0 = time.perf_counter()
                r = c.post("/search", json={"query": q, "top_k": 10})
                t1 = time.perf_counter()
                r.raise_for_status()
                latencies.append((t1 - t0) * 1000)

    latencies.sort()
    n = len(latencies)
    p50 = latencies[n // 2]
    p95 = latencies[int(n * 0.95)]
    p99 = latencies[int(n * 0.99)]
    print(f"\n{n} requests")
    print(f"p50 = {p50:7.1f} ms")
    print(f"p95 = {p95:7.1f} ms")
    print(f"p99 = {p99:7.1f} ms")
    print(f"min = {min(latencies):7.1f} ms")
    print(f"max = {max(latencies):7.1f} ms")
    print(f"avg = {statistics.mean(latencies):7.1f} ms")

if __name__ == "__main__":
    main()

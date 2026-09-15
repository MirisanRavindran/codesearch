from prometheus_client import Counter, Histogram

SEARCH_REQUESTS = Counter(
    "codesearch_search_requests_total",
    "Total /search requests",
    labelnames=["status"],  # "ok" | "error"
)

SEARCH_LATENCY = Histogram(
    "codesearch_search_latency_seconds",
    "End-to-end /search latency in seconds",
    # Buckets tuned for a fast search API — most requests should land in the 50-500ms range.
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

SEARCH_ERRORS = Counter(
    "codesearch_search_errors_total",
    "Total /search errors by kind",
    labelnames=["kind"],  # e.g. "validation" | "internal"
)

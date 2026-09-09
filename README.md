# CodeSearch

Semantic search over the top 200 open-source Python repositories on GitHub. Ask a natural-language question like *"parse JSON from an HTTP response with retries"* and get relevant functions from popular libraries with links back to their source on GitHub.

## Architecture

```
┌─────────────────┐     ┌──────────────┐     ┌────────────────┐
│  Ingestion      │───▶ │  Chunks      │───▶ │  Embedding &   │
│  (GitHub API +  │     │  (JSONL)     │     │  FAISS index   │
│   Python AST)   │     │              │     │  (offline)     │
└─────────────────┘     └──────────────┘     └────────────────┘
                                                       │
                                                       ▼
                              ┌──────────────────────────────────┐
                              │  FastAPI /search                 │
                              │  (loads model + index in memory) │
                              └──────────────────────────────────┘
                                                       │
                                                       ▼
                                            ┌────────────────┐
                                            │  React UI      │
                                            │  (Vite)        │
                                            └────────────────┘
```

Three pipelines that run at different cadences:

1. **Ingestion** (offline, ~30 min for 200 repos). Uses GitHub Search API to find top Python repos, downloads tarballs, walks every `.py` file, parses with Python's stdlib `ast`, and emits one JSON chunk per function/class/method to `data/chunks.jsonl`.

2. **Index build** (offline, ~10 min for 300K chunks on CPU). Reads chunks, computes a 384-dim embedding for each with `sentence-transformers/all-MiniLM-L6-v2`, stores in a FAISS `IndexFlatIP` (exact inner-product search).

3. **Search API** (online). FastAPI loads the model + index into memory once at startup. Each `/search` request embeds the query and runs a FAISS top-K search. On a modern laptop, a query over ~300K vectors returns in ~30-80 ms end-to-end.

## Repository layout

```
codesearch/
├── backend/
│   ├── main.py               # FastAPI app + endpoints
│   ├── search.py             # SearchService that ties embedder + index
│   ├── config.py             # Env-var settings (pydantic-settings)
│   ├── models.py             # Pydantic models (CodeChunk, SearchRequest, SearchResponse)
│   ├── metrics.py            # Prometheus counters + latency histogram
│   ├── ingestion/
│   │   ├── github_client.py  # httpx client for GitHub API + tarball extraction
│   │   ├── chunker.py        # AST-based function/class extractor
│   │   └── ingest.py         # main ingestion script (run once)
│   ├── embedding/
│   │   └── embedder.py       # sentence-transformers wrapper
│   └── index/
│       └── faiss_index.py    # FAISS build/save/load/search
├── scripts/
│   └── build_index.py        # embeds chunks and writes the FAISS index
├── frontend/                 # React + Vite UI
├── tests/                    # pytest starter tests
├── Dockerfile                # multi-stage: frontend build + Python runtime
├── docker-compose.yml        # (add for local dev if you want)
├── fly.toml                  # Fly.io deployment config
└── pyproject.toml            # Python dependencies
```

## Local setup

You need Python 3.11+ and Node 20+.

```bash
# 1. Clone and enter
git clone https://github.com/YOUR_USERNAME/codesearch
cd codesearch

# 2. Install Python deps (using uv, or pip works fine)
pip install uv
uv venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
uv pip install -e ".[dev]"

# 3. Set your GitHub token so you don't hit rate limits.
#    Generate at https://github.com/settings/tokens — no scopes needed for public repos.
export GITHUB_TOKEN=ghp_...

# 4. Start small — 10 repos while you're testing the pipeline
export NUM_REPOS_TO_INGEST=10
python -m backend.ingestion.ingest

# 5. Build the FAISS index from the chunks you just ingested
python scripts/build_index.py

# 6. Start the API
uvicorn backend.main:app --reload

# 7. In a second terminal, start the frontend
cd frontend
npm install
npm run dev
# open http://localhost:5173
```

Once you've verified the pipeline works end-to-end with 10 repos, re-run steps 4 and 5 with `NUM_REPOS_TO_INGEST=200` for the full corpus.

## Docker

```bash
# Build
docker build -t codesearch .

# Run — mount your local data dir so it can read the FAISS index
docker run -p 8000:8000 -v $(pwd)/data:/data codesearch
```

## Deploying to Fly.io

```bash
# One-time setup
brew install flyctl        # or curl -L https://fly.io/install.sh | sh
fly auth signup

# Customize fly.toml (change `app = "codesearch-CHANGEME"` to something unique)
fly launch --no-deploy     # generates a fly.toml — merge with the one in this repo

# Create the persistent volume for your FAISS index
fly volumes create codesearch_data --size 1 --region yyz

# Upload your locally built index into the volume
# (Fly.io has SFTP; alternately deploy once with a rebuild step)
fly deploy
```

Once deployed you'll get a public URL like `https://codesearch-mirisan.fly.dev`. Point your frontend at it.

## Benchmarks to run for your resume

Your resume placeholders are `[FILL: XX]K chunks`, `[FILL: XXX]ms latency`, `[FILL: X,XXX] queries from [FILL: XX]+ users`. Fill them with **real numbers you measure**. Don't guess.

**Chunk count**: comes from the ingest output — the last log line reports `X chunks written`. Expect 200-400K for 200 top-starred Python repos.

**Latency**: after the API is running, hit it 100 times with a mix of queries and measure. Simple script:

```python
import httpx, time, statistics
queries = ["parse json", "retry decorator", "sort list", "http client", ...]  # 20+ varied
latencies = []
with httpx.Client(base_url="http://localhost:8000") as c:
    for _ in range(5):
        for q in queries:
            r = c.post("/search", json={"query": q, "top_k": 10}).json()
            latencies.append(r["latency_ms"])
print(f"p50={statistics.median(latencies):.0f}ms  p99={sorted(latencies)[int(len(latencies)*0.99)]:.0f}ms")
```

**Users / queries**: this is the honest hard one. To get real users you'd need to actually share the project. Options:
- Post to r/Python, r/programming, HackerNews — real users but unpredictable numbers
- Share in your school's CS Discord/Slack — smaller numbers but reliable
- If you can't get real external users, change the resume bullet to something you *can* measure, e.g. `served X queries in a two-week self-benchmarking period` or `verified correctness on Y curated queries` — better than an inflated user count you'll get caught on

## What YOU need to build/customize before this is resume-ready

The scaffold works. But if you submit exactly what's in this repo, Google interviewers will spot it — the design choices are too clean and the frontend is too minimal. **You need to make this yours.** Concretely, do at least three of these:

1. **Add BM25 hybrid ranking.** Pure semantic search misses exact-identifier queries. Use `rank_bm25` to score chunks on keyword overlap, normalize both scores to [0,1], and combine with a tunable weight (e.g. `final = 0.7 * semantic + 0.3 * bm25`). Now you have a real system-design story: "why hybrid?"

2. **Add a query-log-driven eval set.** Write 30 queries where you know the "right" answer (e.g. "requests session pooling" should return `requests.Session`). Measure Recall@10 on your index. Now you have "measured retrieval quality Recall@10 = X" for the resume.

3. **Redesign the frontend.** The starter is deliberately ugly. Add syntax highlighting (prism-react-renderer), a decent monospace layout, keyboard nav, dark mode, whatever. The frontend is what recruiters see if they click the URL.

4. **Add per-query result caching.** LRU cache in memory keyed on `(query, top_k)`. Not for scale but for the story: "duplicate queries under 5% latency."

5. **Add rate limiting.** slowapi or just a token-bucket middleware. "Rate-limited to X req/min per IP to protect against abuse."

6. **Switch to an IVF or HNSW index and measure the tradeoff.** FlatIP is O(N*D) per query. IVF/HNSW are sublinear but lossy — quantify the recall drop and the speed gain on your data. Now you have a real applied-systems story.

7. **Add a tree-sitter based chunker for a second language** (Go, JavaScript). Now the project is not just a Python-only demo.

Pick the ones that interest you. If you do 3-4 of these, the project is genuinely yours and you'll have talking points for a whole interview.

## Things you should be able to explain in an interview

If a Google engineer asks any of these, you should have a clear answer:

- **Why FAISS?** vs Annoy, HNSWlib, Weaviate, Pinecone
- **Why `IndexFlatIP` specifically?** vs IndexFlatL2, IndexIVF, IndexHNSW
- **Why `all-MiniLM-L6-v2` for embeddings?** vs code-specific models like CodeBERT
- **Why normalize embeddings?** (Answer: inner product on unit vectors = cosine similarity)
- **What's your chunking strategy and why?** (Function-level via `ast`, preserves semantic boundaries)
- **How would you scale to 10M chunks?** (Switch to IVF or HNSW, batch queries, shard)
- **How would you handle multiple languages?** (Tree-sitter parser per language, same embedder)
- **What would break if you deployed this at 1000 QPS?** (Model becomes CPU bottleneck; add model server with GPU, quantize embeddings, cache queries)
- **What's in your `/metrics` endpoint and why those metrics?** (Rate, latency histogram, error rate — RED method)

If any of those don't feel obvious yet, read the linked code, then read the papers/docs behind each choice. This is your project — own it.

## License

MIT — do whatever you want with it.

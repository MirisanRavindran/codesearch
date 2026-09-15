import { useState } from 'react'

export default function App() {
  const [query, setQuery] = useState('')
  const [hits, setHits] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [latencyMs, setLatencyMs] = useState(null)

  const onSubmit = async (e) => {
    e.preventDefault()
    if (!query.trim()) return
    setLoading(true)
    setError(null)
    try {
      const res = await fetch('/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, top_k: 10 }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setHits(data.hits)
      setLatencyMs(data.latency_ms)
    } catch (err) {
      setError(err.message)
      setHits([])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="app">
      <header>
        <h1>CodeSearch</h1>
        <p className="subtitle">
          Semantic search over the top 200 open-source Python repositories on GitHub.
        </p>
      </header>

      <form onSubmit={onSubmit} className="search-form">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="e.g. parse JSON from HTTP response with retries"
          autoFocus
        />
        <button type="submit" disabled={loading}>
          {loading ? 'searching…' : 'search'}
        </button>
      </form>

      {error && <div className="error">Error: {error}</div>}

      {latencyMs !== null && (
        <div className="meta">
          {hits.length} results in {latencyMs.toFixed(1)}ms
        </div>
      )}

      <ul className="results">
        {hits.map((hit) => (
          <li key={hit.chunk.chunk_id} className="hit">
            <div className="hit-header">
              <a href={hit.chunk.github_url} target="_blank" rel="noreferrer">
                <strong>{hit.chunk.repo}</strong> · {hit.chunk.file_path}
              </a>
              <span className="score">{hit.score.toFixed(3)}</span>
            </div>
            <div className="hit-name">
              {hit.chunk.kind} <code>{hit.chunk.name}</code> · lines{' '}
              {hit.chunk.start_line}–{hit.chunk.end_line}
            </div>
            {hit.chunk.docstring && (
              <p className="docstring">{hit.chunk.docstring.slice(0, 240)}…</p>
            )}
            <pre className="source">{hit.chunk.source.slice(0, 800)}</pre>
          </li>
        ))}
      </ul>
    </div>
  )
}

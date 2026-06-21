import { useCallback, useEffect, useRef, useState } from "react";
import {
  fetchCacheDebug,
  fetchSuggestions,
  fetchTrending,
  submitSearch,
} from "./api.js";
import "./App.css";

function useDebouncedValue(value, delayMs = 150) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);
  return debounced;
}

export default function App() {
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState("basic");
  const [suggestions, setSuggestions] = useState([]);
  const [trending, setTrending] = useState([]);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [searchResult, setSearchResult] = useState("");
  const [cacheInfo, setCacheInfo] = useState(null);
  const [activeIndex, setActiveIndex] = useState(-1);
  const inputRef = useRef(null);
  const debouncedQuery = useDebouncedValue(query, 150);

  const loadTrending = useCallback(async () => {
    try {
      const data = await fetchTrending("trending");
      setTrending(data.trending || []);
    } catch (err) {
      setError(err.message);
    }
  }, []);

  useEffect(() => {
    loadTrending();
  }, [loadTrending]);

  useEffect(() => {
    setSuggestions([]);
    setActiveIndex(-1);
    if (!query.trim()) {
      setCacheInfo(null);
    }
  }, [query]);

  useEffect(() => {
    let cancelled = false;

    async function loadSuggestions() {
      setError("");
      if (!debouncedQuery.trim()) {
        setSuggestions([]);
        setCacheInfo(null);
        setActiveIndex(-1);
        return;
      }

      setLoading(true);
      try {
        const [suggestData, debugData] = await Promise.all([
          fetchSuggestions(debouncedQuery, mode),
          fetchCacheDebug(debouncedQuery),
        ]);
        if (cancelled) return;
        setSuggestions(suggestData.suggestions || []);
        setCacheInfo({
          node: suggestData.cache?.node,
          hit: suggestData.cache?.hit,
          debug: debugData,
        });
        setActiveIndex(-1);
      } catch (err) {
        if (!cancelled) setError(err.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadSuggestions();
    return () => {
      cancelled = true;
    };
  }, [debouncedQuery, mode]);

  const runSearch = async (selectedQuery) => {
    const value = (selectedQuery ?? query).trim();
    if (!value) return;
    setError("");
    setSubmitting(true);
    try {
      const result = await submitSearch(value);
      setSearchResult(result.message);
      setQuery(value);
      await loadTrending();
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const onKeyDown = (event) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((idx) => Math.min(idx + 1, suggestions.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((idx) => Math.max(idx - 1, -1));
    } else if (event.key === "Enter") {
      event.preventDefault();
      if (activeIndex >= 0 && suggestions[activeIndex]) {
        runSearch(suggestions[activeIndex].query);
      } else {
        runSearch();
      }
    } else if (event.key === "Escape") {
      setSuggestions([]);
      setActiveIndex(-1);
    }
  };

  return (
    <div className="page">
      <header className="hero">
        <p className="eyebrow">HLD101 Assignment</p>
        <h1>Search Typeahead</h1>
        <p className="subtitle">
          Prefix suggestions ranked by popularity, with distributed Redis caching and batch search writes.
        </p>
      </header>

      <main className="layout">
        <section className="panel search-panel">
          <label htmlFor="search-input">Search</label>
          <div className="search-row">
            <input
              id="search-input"
              ref={inputRef}
              type="text"
              value={query}
              placeholder="Try goog, face, video..."
              autoComplete="off"
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={onKeyDown}
            />
            <button type="button" onClick={() => runSearch()} disabled={submitting || loading}>
              Search
            </button>
          </div>

          <div className="mode-toggle">
            <button
              type="button"
              className={mode === "basic" ? "active" : ""}
              onClick={() => setMode("basic")}
            >
              Basic ranking
            </button>
            <button
              type="button"
              className={mode === "trending" ? "active" : ""}
              onClick={() => setMode("trending")}
            >
              Trending ranking
            </button>
          </div>

          {loading && <p className="status">Loading suggestions...</p>}
          {submitting && <p className="status">Submitting search...</p>}
          {error && <p className="status error">{error}</p>}
          {searchResult && <p className="status success">API response: {searchResult}</p>}

          {cacheInfo && debouncedQuery && (
            <p className="cache-debug">
              Cache node: <strong>{cacheInfo.node || "none"}</strong> ·{" "}
              {cacheInfo.hit ? "HIT" : "MISS"}
            </p>
          )}

          {suggestions.length > 0 && (
            <ul className="suggestions" role="listbox">
              {suggestions.map((item, index) => (
                <li
                  key={item.query}
                  role="option"
                  aria-selected={index === activeIndex}
                  className={index === activeIndex ? "active" : ""}
                  onMouseDown={() => runSearch(item.query)}
                >
                  <span>{item.query}</span>
                  <span className="count">{item.count.toLocaleString()}</span>
                </li>
              ))}
            </ul>
          )}

          {!loading && debouncedQuery && suggestions.length === 0 && (
            <p className="status">No suggestions for this prefix.</p>
          )}
        </section>

        <aside className="panel trending-panel">
          <h2>Trending Searches</h2>
          <p className="muted">Recency-aware ranking (0.6 global + 0.3 weekly + 0.1 daily)</p>
          <ol>
            {trending.map((item) => (
              <li key={item.query}>
                <button type="button" onClick={() => runSearch(item.query)}>
                  {item.query}
                </button>
                <span>{Math.round(item.score).toLocaleString()}</span>
              </li>
            ))}
          </ol>
        </aside>
      </main>
    </div>
  );
}

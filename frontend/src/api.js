const API_BASE = import.meta.env.VITE_API_BASE || "/api";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed: ${response.status}`);
  }
  return response.json();
}

export function fetchSuggestions(prefix, mode = "basic") {
  const params = new URLSearchParams({ q: prefix, mode, limit: "10" });
  return request(`/suggest?${params.toString()}`);
}

export function submitSearch(query) {
  return request("/search", {
    method: "POST",
    body: JSON.stringify({ query }),
  });
}

export function fetchTrending(mode = "trending") {
  const params = new URLSearchParams({ mode, limit: "10" });
  return request(`/trending?${params.toString()}`);
}

export function fetchCacheDebug(prefix) {
  const params = new URLSearchParams({ prefix, mode: "basic" });
  return request(`/cache/debug?${params.toString()}`);
}

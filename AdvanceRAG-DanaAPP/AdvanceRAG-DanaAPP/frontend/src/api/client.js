// Thin fetch wrapper around our own FastAPI backend.
// VITE_API_BASE_URL="" (explicitly empty, e.g. in the production build) means
// "same origin" — requests go to relative paths and a reverse proxy (Caddy)
// routes them to the backend. Only when the variable is completely unset do
// we fall back to the local-dev default.
const API_BASE = import.meta.env.VITE_API_BASE_URL !== undefined
  ? import.meta.env.VITE_API_BASE_URL
  : 'http://localhost:8000';

async function doFetch(path, options) {
  const isFormData = options.body instanceof FormData;
  return fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
      ...options.headers,
    },
  });
}

export async function apiFetch(path, options = {}) {
  const res = await doFetch(path, options);

  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const data = await res.json();
      detail = data.detail || detail;
    } catch {
      /* ignore non-JSON error bodies */
    }
    const err = new Error(detail);
    err.status = res.status;
    throw err;
  }

  return res;
}

export async function apiJson(path, options = {}) {
  const res = await apiFetch(path, options);
  return res.status === 204 ? null : res.json();
}

export { API_BASE };

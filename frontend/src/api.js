// Pona API client.
//
// In development, Vite proxies /api -> http://localhost:8000 (vite.config.js).
// In production there is no proxy, so the deployed API URL comes from
// VITE_API_URL at build time (set it in the host's env, e.g.
// VITE_API_URL=https://pona-api.onrender.com).
//
// Vite inlines env vars at BUILD time, not runtime: changing it on the host
// requires a rebuild, not just a restart.

const BASE = import.meta.env.VITE_API_URL?.replace(/\/$/, '') || '/api'

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    let detail = `Request failed (${res.status})`
    try {
      const body = await res.json()
      if (body.detail) detail = body.detail
    } catch {
      // response wasn't JSON; keep the status message
    }
    throw new Error(detail)
  }
  return res.json()
}

/** Every condition Pona can check. Comes from the knowledge base, never hardcoded here. */
export const getConditions = () => request('/conditions/')

/** Which input methods actually work on this server. Never offer a button that can't work. */
export const getCapabilities = () => request('/scan/capabilities')

/**
 * Read text from a photo of an ingredient label.
 *
 * Returns { text, confidence, word_count, reliable, warnings }.
 *
 * This deliberately does NOT check the food. OCR fails by dropping words
 * silently, so the extracted text goes to the user for review first — the
 * person holding the packet can see whether it matches.
 */
export async function readLabelPhoto(file) {
  const form = new FormData()
  form.append('file', file)
  // No Content-Type header: the browser must set the multipart boundary.
  const res = await fetch(`${BASE}/scan/ocr`, { method: 'POST', body: form })
  if (!res.ok) {
    let detail = `Could not read that image (${res.status})`
    try {
      const body = await res.json()
      if (body.detail) detail = body.detail
    } catch {
      /* keep the status message */
    }
    throw new Error(detail)
  }
  return res.json()
}

export const createProfile = (body) =>
  request('/profile/', { method: 'POST', body: JSON.stringify(body) })

export const getProfile = (id) => request(`/profile/${id}`)

/** The profile rendered for a kitchen. Regenerated per request so it cannot go stale. */
export const getChefCard = (id) => request(`/profile/${id}/chef-card`)

/** Look up a scanned barcode. Returns the product for the user to confirm. */
export const lookupBarcode = (code) =>
  request('/scan/barcode', { method: 'POST', body: JSON.stringify({ code }) })

export const updateProfile = (id, body) =>
  request(`/profile/${id}`, { method: 'PUT', body: JSON.stringify(body) })

export const checkFood = (profileId, ingredients) =>
  request('/verdict/', {
    method: 'POST',
    body: JSON.stringify({ profile_id: profileId, ingredients }),
  })

// ── Local profile identity ───────────────────────────────────────────────
//
// MVP has no accounts. The profile id lives in this browser, which is
// enough to use the app and avoids collecting anything about anyone.
// Wrapped in try/catch because storage throws outright in some private
// browsing modes rather than just returning null.

const KEY = 'pona.profileId'

export function getStoredProfileId() {
  try {
    const v = localStorage.getItem(KEY)
    return v ? Number(v) : null
  } catch {
    return null
  }
}

export function storeProfileId(id) {
  try {
    localStorage.setItem(KEY, String(id))
  } catch {
    // Non-fatal: the session still works, it just won't be remembered.
  }
}

export function clearStoredProfile() {
  try {
    localStorage.removeItem(KEY)
  } catch {
    /* nothing to do */
  }
}

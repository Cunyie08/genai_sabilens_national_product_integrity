/**
 * SabiLens API client.
 *
 * All backend calls go through this module so the base URL is configured
 * in one place (VITE_API_BASE_URL in .env).
 */

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

/**
 * Generic fetch wrapper with JSON handling and error normalisation.
 */
async function request(path, options = {}) {
  const url = `${BASE_URL}${path}`;

  const defaultHeaders = { 'Content-Type': 'application/json' };

  // Attach JWT if stored
  const token = localStorage.getItem('accessToken');
  if (token) {
    defaultHeaders['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(url, {
    ...options,
    headers: { ...defaultHeaders, ...(options.headers || {}) },
  });

  let body;
  try {
    body = await res.json();
  } catch {
    body = { success: false, message: `HTTP ${res.status}` };
  }

  if (!res.ok) {
    const msg =
      body?.detail ||
      body?.message ||
      `Request failed with status ${res.status}`;
    throw new Error(msg);
  }

  return body;
}

// ── Auth ──────────────────────────────────────────────────────────────────────

export const authApi = {
  register: (payload) =>
    request('/api/v1/auth/register', { method: 'POST', body: JSON.stringify(payload) }),

  login: (payload) =>
    request('/api/v1/auth/login', { method: 'POST', body: JSON.stringify(payload) }),
};

// ── Consumer Scan ─────────────────────────────────────────────────────────────

export const scanApi = {
  /**
   * Submit a product scan.
   *
   * @param {object} payload
   * @param {string} payload.image_data  - base64 data-URL or remote image URL
   * @param {string} [payload.nafdac_no]
   * @param {string} [payload.category]
   * @param {number} [payload.latitude]
   * @param {number} [payload.longitude]
   * @param {string} [payload.location_text]
   * @param {string} [payload.purchase_channel]
   * @param {string} [payload.product_name]
   */
  submitScan: (payload) =>
    request('/api/consumer/scan', { method: 'POST', body: JSON.stringify(payload) }),

  /** Liveness check for the consumer scan service. */
  health: () => request('/api/consumer/scan/health'),
};

// ── Verification ──────────────────────────────────────────────────────────────

export const verifyApi = {
  nafdac: (number) => request(`/api/verify/nafdac/${encodeURIComponent(number)}`),
  batch: (number) => request(`/api/verify/batch/${encodeURIComponent(number)}`),
};

// ── Location ──────────────────────────────────────────────────────────────────

export const locationApi = {
  states: () => request('/api/location/states'),
  cities: (state) => request(`/api/location/cities/${encodeURIComponent(state)}`),
};

export default { authApi, scanApi, verifyApi, locationApi };

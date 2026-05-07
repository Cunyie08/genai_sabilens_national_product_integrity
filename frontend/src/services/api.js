/**
 * SabiLens API client.
 *
 * All backend calls go through this module so the base URL is configured
 * in one place (VITE_API_BASE_URL in .env).
 */

// When accessed from a phone over the local network the hostname is the
// laptop's network IP (e.g. 10.231.18.72), not "localhost".  Using
// window.location.hostname means every device automatically talks to the
// right host without any hardcoding.  VITE_API_BASE_URL overrides this for
// staging / production deployments.
const BASE_URL =
  import.meta.env.VITE_API_BASE_URL ||
  'https://sabilens.com/api';

/**
 * Generic fetch wrapper with JSON handling, error normalisation, and timeout.
 *
 * @param {string} path
 * @param {RequestInit} options
 * @param {number} timeoutMs  Abort after this many ms (default 30 s).
 *                            Pass a larger value for long-running endpoints
 *                            like /consumer/scan (image upload + AI pipeline).
 */
async function request(path, options = {}, timeoutMs = 30000) {
  const url = `${BASE_URL}${path}`;

  const defaultHeaders = { 'Content-Type': 'application/json' };

  // Attach JWT if stored
  const token = localStorage.getItem('accessToken');
  if (token) {
    defaultHeaders['Authorization'] = `Bearer ${token}`;
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const res = await fetch(url, {
      ...options,
      signal: controller.signal,
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
      const err = new Error(msg);
      err.status = res.status;
      throw err;
    }

    return body;
  } catch (err) {
    if (err.name === 'AbortError') {
      throw new Error('Request timed out. Please check your connection and try again.');
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

// ── Auth ──────────────────────────────────────────────────────────────────────

export const authApi = {
  register: (payload) =>
    request('/api/v1/auth/register', { method: 'POST', body: JSON.stringify(payload) }),

  login: (payload) =>
    request('/api/v1/auth/login', { method: 'POST', body: JSON.stringify(payload) }),

  // Get current user profile
  getProfile: () =>
    request('/api/v1/auth/me', { method: 'GET' }),

  // Update user profile
  updateProfile: (payload) =>
    request('/api/v1/auth/profile', { method: 'PUT', body: JSON.stringify(payload) }),
};

// ── Consumer Scan ─────────────────────────────────────────────────────────────

export const scanApi = {
  /**
   * Submit a product scan.
   *
   * @param {object} payload
   * @param {string} payload.image_data  - base64 data-URL or remote image URL
   * @param {string} [payload.back_image_data] - back/side panel image
   * @param {string} [payload.nafdac_no]
   * @param {string} [payload.category]
   * @param {number} [payload.latitude]
   * @param {number} [payload.longitude]
   * @param {string} [payload.location_text]
   * @param {string} [payload.purchase_channel]
   * @param {string} [payload.product_name]
   */
  submitScan: (payload) =>
    request('/api/consumer/scan', { method: 'POST', body: JSON.stringify(payload) }, 120000),

  /**
   * Quick product detection for front panel.
   * Checks if a product is present in the captured image.
   *
   * @param {object} payload
   * @param {string} payload.image_data - base64 image data (without data:image prefix or with)
   * @param {string} [payload.phase] - 'front' or 'back' (default: 'front')
   * @returns {Promise<{has_product: boolean, confidence: number, message: string}>}
   */
  detectProduct: (payload) =>
    request('/api/consumer/scan/detect-product', { method: 'POST', body: JSON.stringify(payload) }),

  /** Liveness check for the consumer scan service. */
  health: () => request('/api/consumer/scan/health'),

  /** Create a QR cross-device scan session. Returns {session_id, mobile_url}. */
  createSession: () =>
    request('/api/v1/scan/session', { method: 'POST' }),

  /** Poll session status — 'pending' | 'location_ready' | 'complete' | 'expired'. */
  getSessionStatus: (sessionId) =>
    request(`/api/v1/scan/session/${sessionId}/status`),

  /** Phone calls this to push its GPS fix to the desktop session. */
  submitPhoneLocation: (sessionId, { latitude, longitude }) =>
    request(`/api/v1/scan/session/${sessionId}/location`, {
      method: 'PUT',
      body: JSON.stringify({ latitude, longitude }),
    }),

  // ── Scan History Endpoints ─────────────────────────────────────────────────

  /**
   * Get user's scan history
   * @param {number} limit - Maximum number of scans to return (default: 100)
   * @param {number} offset - Number of scans to skip (for pagination)
   */
  getScanHistory: (limit = 100, offset = 0) =>
    request(`/api/consumer/scans?limit=${limit}&offset=${offset}`, { method: 'GET' }),

  /**
   * Get a specific scan by ID
   * @param {string} scanId - UUID of the scan
   */
  getScanById: (scanId) =>
    request(`/api/consumer/scan/${scanId}`, { method: 'GET' }),

  /**
   * Save a scan to history
   * @param {object} payload - Scan data to save
   */
  saveScan: (payload) =>
    request('/api/consumer/scans', { method: 'POST', body: JSON.stringify(payload) }),

  /**
   * Delete a specific scan
   * @param {string} scanId - UUID of the scan to delete
   */
  deleteScan: (scanId) =>
    request(`/api/consumer/scan/${scanId}`, { method: 'DELETE' }),

  /**
   * Clear all scan history for current user
   */
  clearScanHistory: () =>
    request('/api/consumer/scans/clear', { method: 'DELETE' }),
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
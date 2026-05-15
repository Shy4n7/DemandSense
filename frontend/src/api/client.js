/**
 * API client for DemandSense backend endpoints.
 * Each function uses AbortController with a 12-second timeout and throws
 * a typed error on non-2xx responses.
 *
 * Requirements: 4.9, 8.2, 13.2
 */

const TIMEOUT_MS = 12_000;

/**
 * Typed error for non-2xx API responses.
 */
export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

/**
 * Internal helper: fetch with a 12-second AbortController timeout.
 * Throws ApiError on non-2xx responses.
 */
async function fetchWithTimeout(url, options = {}) {
  const controller = new AbortController();
  const timerId = setTimeout(() => controller.abort(), TIMEOUT_MS);

  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
    });

    if (!response.ok) {
      let errorMessage = `HTTP ${response.status}`;
      try {
        const body = await response.json();
        if (body && body.error) {
          errorMessage = body.error;
        }
      } catch {
        // If the body isn't JSON, fall back to the status text
        errorMessage = response.statusText || errorMessage;
      }
      throw new ApiError(response.status, errorMessage);
    }

    return response.json();
  } finally {
    clearTimeout(timerId);
  }
}

/**
 * Fetch the list of available products.
 * GET /api/products
 * @returns {Promise<Array<{product_id: string, description: string}>>}
 */
export async function fetchProducts() {
  return fetchWithTimeout('/api/products');
}

/**
 * Fetch a demand forecast for a product.
 * POST /api/forecast
 * @param {string} productId
 * @param {7|14|30} horizonDays
 * @returns {Promise<{product_id: string, forecast: Array, metrics: {mape: number, rmse: number}}>}
 */
export async function fetchForecast(productId, horizonDays) {
  return fetchWithTimeout('/api/forecast', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ product_id: productId, horizon_days: horizonDays }),
  });
}

/**
 * Fetch anomaly records for a product.
 * POST /api/anomalies
 * @param {string} productId
 * @returns {Promise<{product_id: string, anomalies: Array, total_anomalies: number}>}
 */
export async function fetchAnomalies(productId) {
  return fetchWithTimeout('/api/anomalies', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ product_id: productId }),
  });
}

/**
 * Fetch feature importances for a product's forecast model.
 * GET /api/importance?product_id=
 * @param {string} productId
 * @returns {Promise<{product_id: string, features: Array<{name: string, importance: number}>}>}
 */
export async function fetchImportance(productId) {
  const params = new URLSearchParams({ product_id: productId });
  return fetchWithTimeout(`/api/importance?${params}`);
}

/**
 * Fetch inventory replenishment metrics for a product.
 * GET /api/inventory?product_id=&current_stock=&lead_time=&service_level=
 * @param {string} productId
 * @param {number} currentStock   — Current on-hand inventory (≥ 0)
 * @param {number} leadTime       — Supplier lead time in days (1–90)
 * @param {number} [serviceLevel] — Service level probability (default 0.95)
 * @returns {Promise<{
 *   product_id: string,
 *   forecasted_demand: number,
 *   safety_stock: number,
 *   reorder_point: number,
 *   current_stock: number,
 *   suggested_order: number,
 *   status: 'SUFFICIENT' | 'REORDER NOW' | 'CRITICAL',
 *   reorder_alert: boolean
 * }>}
 */
export async function fetchInventory(productId, currentStock, leadTime, serviceLevel = 0.95) {
  const params = new URLSearchParams({
    product_id: productId,
    current_stock: String(currentStock),
    lead_time: String(leadTime),
    service_level: String(serviceLevel),
  });
  return fetchWithTimeout(`/api/inventory?${params}`);
}

/**
 * Fetch historical daily quantities for a product (used by simulation).
 * GET /api/simulation?product_id=
 * @param {string} productId
 * @returns {Promise<{
 *   product_id: string,
 *   data: Array<{date: string, actual_quantity: number}>,
 *   total_days: number
 * }>}
 */
export async function fetchSimulationData(productId) {
  const params = new URLSearchParams({ product_id: productId });
  return fetchWithTimeout(`/api/simulation?${params}`);
}

/**
 * InventoryPanel — Inventory replenishment suggestion panel.
 *
 * Accepts a product_id prop, lets the user enter current stock, lead time,
 * and service level, then calls the /api/inventory endpoint and displays
 * the replenishment metrics.
 */

import { useState } from 'react';
import { fetchInventory } from '../api/client';
import SkeletonLoader from './SkeletonLoader';
import ErrorMessage from './ErrorMessage';

// ---------------------------------------------------------------------------
// Status badge colours
// ---------------------------------------------------------------------------

const STATUS_STYLES = {
  SUFFICIENT: 'bg-green-100 text-green-800',
  'REORDER NOW': 'bg-amber-100 text-amber-800',
  CRITICAL: 'bg-red-100 text-red-800',
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * @param {object}      props
 * @param {string|null} props.selectedProduct — Currently selected product_id
 */
export default function InventoryPanel({ selectedProduct }) {
  const [currentStock, setCurrentStock] = useState('');
  const [leadTime, setLeadTime] = useState('');
  const [serviceLevel, setServiceLevel] = useState('0.95');

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  // -------------------------------------------------------------------------
  // Form submission
  // -------------------------------------------------------------------------

  async function handleSubmit(e) {
    e.preventDefault();

    if (!selectedProduct) return;

    const stockVal = parseFloat(currentStock);
    const leadVal = parseInt(leadTime, 10);

    if (isNaN(stockVal) || stockVal < 0) {
      setError('Current stock must be a number ≥ 0.');
      return;
    }
    if (isNaN(leadVal) || leadVal < 1 || leadVal > 90) {
      setError('Lead time must be an integer between 1 and 90.');
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const data = await fetchInventory(
        selectedProduct,
        stockVal,
        leadVal,
        parseFloat(serviceLevel),
      );
      setResult(data);
    } catch (err) {
      setError(err.message || 'Failed to calculate inventory.');
    } finally {
      setLoading(false);
    }
  }

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  return (
    <div className="rounded-xl border border-gray-200 bg-white shadow-sm">
      {/* Header */}
      <div className="border-b border-gray-100 px-5 py-4">
        <h2 className="text-base font-semibold text-gray-800">
          Inventory Replenishment
        </h2>
        <p className="mt-0.5 text-xs text-gray-500">
          Calculate safety stock and reorder point based on demand forecast
        </p>
      </div>

      {/* Form */}
      <form onSubmit={handleSubmit} className="px-5 py-4">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {/* Current Stock */}
          <div>
            <label
              htmlFor="current-stock"
              className="mb-1 block text-xs font-medium text-gray-700"
            >
              Current Stock (units)
            </label>
            <input
              id="current-stock"
              type="number"
              min="0"
              step="1"
              placeholder="e.g. 500"
              value={currentStock}
              onChange={(e) => setCurrentStock(e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              required
            />
          </div>

          {/* Lead Time */}
          <div>
            <label
              htmlFor="lead-time"
              className="mb-1 block text-xs font-medium text-gray-700"
            >
              Lead Time (days)
            </label>
            <input
              id="lead-time"
              type="number"
              min="1"
              max="90"
              step="1"
              placeholder="e.g. 14"
              value={leadTime}
              onChange={(e) => setLeadTime(e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
              required
            />
          </div>

          {/* Service Level */}
          <div>
            <label
              htmlFor="service-level"
              className="mb-1 block text-xs font-medium text-gray-700"
            >
              Service Level
            </label>
            <select
              id="service-level"
              value={serviceLevel}
              onChange={(e) => setServiceLevel(e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            >
              <option value="0.90">90%</option>
              <option value="0.95">95%</option>
              <option value="0.99">99%</option>
            </select>
          </div>
        </div>

        <div className="mt-4">
          <button
            type="submit"
            disabled={loading || !selectedProduct}
            className="rounded-lg bg-blue-600 px-5 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {loading ? 'Calculating…' : 'Calculate'}
          </button>
          {!selectedProduct && (
            <span className="ml-3 text-xs text-gray-400">
              Select a product first
            </span>
          )}
        </div>
      </form>

      {/* Results area */}
      <div className="px-5 pb-5">
        {/* Loading */}
        {loading && (
          <div className="mt-2">
            <SkeletonLoader rows={4} />
          </div>
        )}

        {/* Error */}
        {!loading && error && (
          <ErrorMessage
            message={`Failed to load inventory data. ${error}`}
            onRetry={null}
          />
        )}

        {/* Reorder alert banner */}
        {!loading && result?.reorder_alert && (
          <div
            className="mb-4 flex items-start gap-2 rounded-lg border border-red-300 bg-red-50 px-4 py-3"
            role="alert"
          >
            <span className="text-lg leading-none">⚠</span>
            <p className="text-sm font-semibold text-red-700">
              Reorder{' '}
              <span className="font-bold">
                {result.suggested_order.toLocaleString(undefined, {
                  maximumFractionDigits: 0,
                })}
              </span>{' '}
              units now
            </p>
          </div>
        )}

        {/* Metrics grid */}
        {!loading && result && (
          <div className="space-y-4">
            {/* Top row: 3 metrics */}
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <MetricTile
                label="Forecasted Demand"
                value={result.forecasted_demand.toLocaleString(undefined, {
                  maximumFractionDigits: 1,
                })}
                unit="units"
              />
              <MetricTile
                label="Safety Stock"
                value={result.safety_stock.toLocaleString(undefined, {
                  maximumFractionDigits: 1,
                })}
                unit="units"
              />
              <MetricTile
                label="Reorder Point"
                value={result.reorder_point.toLocaleString(undefined, {
                  maximumFractionDigits: 1,
                })}
                unit="units"
              />
            </div>

            {/* Bottom row: suggested order + status */}
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              <MetricTile
                label="Suggested Order"
                value={result.suggested_order.toLocaleString(undefined, {
                  maximumFractionDigits: 0,
                })}
                unit="units"
                highlight={result.reorder_alert}
              />

              {/* Status badge */}
              <div className="rounded-lg border border-gray-100 bg-gray-50 p-4">
                <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                  Status
                </p>
                <div className="mt-2">
                  <span
                    className={`inline-block rounded-full px-3 py-1 text-sm font-semibold ${
                      STATUS_STYLES[result.status] ?? 'bg-gray-100 text-gray-700'
                    }`}
                  >
                    {result.status}
                  </span>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-component: individual metric tile
// ---------------------------------------------------------------------------

function MetricTile({ label, value, unit, highlight = false }) {
  return (
    <div
      className={`rounded-lg border p-4 ${
        highlight
          ? 'border-red-200 bg-red-50'
          : 'border-gray-100 bg-gray-50'
      }`}
    >
      <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
        {label}
      </p>
      <p
        className={`mt-1 text-2xl font-bold ${
          highlight ? 'text-red-700' : 'text-gray-900'
        }`}
      >
        {value}
      </p>
      {unit && (
        <p className="mt-0.5 text-xs text-gray-400">{unit}</p>
      )}
    </div>
  );
}

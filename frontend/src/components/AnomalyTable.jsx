/**
 * AnomalyTable — filterable table of detected anomaly records.
 *
 * Requirements: 11.1, 11.2, 11.3, 11.4, 11.5
 */

import { useState } from 'react';
import SkeletonLoader from './SkeletonLoader';
import ErrorMessage from './ErrorMessage';

const FILTERS = [
  { label: 'All', value: 'all' },
  { label: 'Demand Spike', value: 'demand_spike' },
  { label: 'Price Anomaly', value: 'price_anomaly' },
  { label: 'Stockout Signal', value: 'stockout_signal' },
];

/**
 * @param {object} props
 * @param {{ anomalies: Array<{date: string, quantity: number, unit_price: number, anomaly_score: number, is_anomaly: boolean, reason: string}> } | null} props.anomalies
 * @param {boolean} props.loading
 * @param {string|null} props.error
 * @param {function} [props.onRetry]
 */
export default function AnomalyTable({
  anomalies = null,
  loading = false,
  error = null,
  onRetry,
}) {
  const [activeFilter, setActiveFilter] = useState('all');

  if (loading) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
        <SkeletonLoader rows={5} />
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
        <ErrorMessage
          message={`Failed to load anomaly data. ${error}`}
          onRetry={onRetry}
        />
      </div>
    );
  }

  // Accept either an object with .anomalies array or a plain array
  const anomalyRows = Array.isArray(anomalies)
    ? anomalies
    : (anomalies?.anomalies ?? []);

  const filtered =
    activeFilter === 'all'
      ? anomalyRows
      : anomalyRows.filter((a) => a.reason === activeFilter);

  return (
    <div className="rounded-xl border border-gray-200 bg-white shadow-sm">
      {/* Header */}
      <div className="border-b border-gray-100 px-5 py-4">
        <h2 className="text-base font-semibold text-gray-800">Anomaly Records</h2>

        {/* Filter chips */}
        <div className="mt-3 flex flex-wrap gap-2" role="group" aria-label="Filter anomalies">
          {FILTERS.map((f) => (
            <button
              key={f.value}
              onClick={() => setActiveFilter(f.value)}
              className={`rounded-full px-3 py-1 text-xs font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1 ${
                activeFilter === f.value
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
              aria-pressed={activeFilter === f.value}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      {filtered.length === 0 ? (
        <div className="px-5 py-10 text-center text-sm text-gray-500">
          No anomalies detected for this product.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">
                <th className="px-4 py-3">Date</th>
                <th className="px-4 py-3">Quantity</th>
                <th className="px-4 py-3">Unit Price</th>
                <th className="px-4 py-3">Anomaly Score</th>
                <th className="px-4 py-3">Reason</th>
                <th className="px-4 py-3">Flag</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((row, idx) => (
                <AnomalyRow key={`${row.date}-${idx}`} row={row} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function AnomalyRow({ row }) {
  const score = row.anomaly_score;

  // Row highlighting based on anomaly_score thresholds (Requirements 11.4)
  let rowClass = '';
  if (score < -0.1) {
    rowClass = 'bg-red-50';
  } else if (score >= -0.1 && score <= 0.0) {
    rowClass = 'bg-amber-50';
  }

  return (
    <tr className={`border-b border-gray-50 last:border-0 ${rowClass}`}>
      <td className="px-4 py-2.5 font-mono text-xs text-gray-700">{row.date}</td>
      <td className="px-4 py-2.5 text-gray-800">{row.quantity?.toLocaleString()}</td>
      <td className="px-4 py-2.5 text-gray-800">
        {row.unit_price != null ? `£${row.unit_price.toFixed(2)}` : '—'}
      </td>
      <td className="px-4 py-2.5 font-mono text-xs text-gray-700">
        {score != null ? score.toFixed(4) : '—'}
      </td>
      <td className="px-4 py-2.5">
        <ReasonBadge reason={row.reason} />
      </td>
      <td className="px-4 py-2.5">
        <FlagBadge isAnomaly={row.is_anomaly} />
      </td>
    </tr>
  );
}

function ReasonBadge({ reason }) {
  const styles = {
    demand_spike: 'bg-red-100 text-red-700',
    price_anomaly: 'bg-purple-100 text-purple-700',
    stockout_signal: 'bg-amber-100 text-amber-700',
    isolation_forest: 'bg-gray-100 text-gray-600',
  };
  const labels = {
    demand_spike: 'Demand Spike',
    price_anomaly: 'Price Anomaly',
    stockout_signal: 'Stockout Signal',
    isolation_forest: 'Isolation Forest',
  };

  const cls = styles[reason] || 'bg-gray-100 text-gray-600';
  const label = labels[reason] || reason;

  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${cls}`}>
      {label}
    </span>
  );
}

function FlagBadge({ isAnomaly }) {
  return isAnomaly ? (
    <span className="inline-block rounded-full bg-red-500 px-2 py-0.5 text-xs font-semibold text-white">
      Anomaly
    </span>
  ) : (
    <span className="inline-block rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700">
      Normal
    </span>
  );
}

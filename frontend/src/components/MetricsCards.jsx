/**
 * MetricsCards — displays MAPE, RMSE, and Total Anomalies metric cards.
 *
 * Requirements: 10.1, 10.2, 10.3, 10.5
 */

import SkeletonLoader from './SkeletonLoader';

/**
 * @param {object} props
 * @param {{ metrics: { mape: number, rmse: number } } | null} props.forecast
 * @param {{ total_anomalies: number } | null} props.anomalies
 * @param {boolean} props.loadingForecast
 * @param {boolean} props.loadingAnomalies
 * @param {string|null} props.errorForecast
 * @param {string|null} props.errorAnomalies
 */
export default function MetricsCards({
  forecast = null,
  anomalies = null,
  loadingForecast = false,
  loadingAnomalies = false,
  errorForecast = null,
  errorAnomalies = null,
}) {
  const mape = forecast?.metrics?.mape ?? null;
  const rmse = forecast?.metrics?.rmse ?? null;
  const totalAnomalies = anomalies?.total_anomalies ?? null;

  const cards = [
    {
      key: 'mape',
      label: 'MAPE',
      value: mape != null ? `${mape.toFixed(2)}%` : null,
      loading: loadingForecast,
      error: errorForecast,
      description: 'Mean Absolute Percentage Error',
    },
    {
      key: 'rmse',
      label: 'RMSE',
      value: rmse != null ? rmse.toFixed(2) : null,
      loading: loadingForecast,
      error: errorForecast,
      description: 'Root Mean Squared Error',
    },
    {
      key: 'anomalies',
      label: 'Total Anomalies',
      value: totalAnomalies != null ? String(totalAnomalies) : null,
      loading: loadingAnomalies,
      error: errorAnomalies,
      description: 'Flagged anomaly records',
    },
  ];

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
      {cards.map((card) => (
        <MetricCard
          key={card.key}
          label={card.label}
          value={card.value}
          description={card.description}
          loading={card.loading}
          error={card.error}
        />
      ))}
    </div>
  );
}

function MetricCard({ label, value, description, loading, error }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
        {label}
      </p>

      {loading ? (
        <div className="mt-3">
          <SkeletonLoader rows={2} />
        </div>
      ) : error ? (
        <p className="mt-2 text-sm font-medium text-red-600" role="alert">
          {error}
        </p>
      ) : (
        <p className="mt-2 text-3xl font-bold text-gray-900">
          {value ?? 'N/A'}
        </p>
      )}

      <p className="mt-1 text-xs text-gray-400">{description}</p>
    </div>
  );
}

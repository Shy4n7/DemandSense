/**
 * ForecastChart — Recharts ComposedChart showing historical actuals,
 * forecast predicted values, and a confidence band.
 *
 * Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6
 */

import {
  ComposedChart,
  Line,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import SkeletonLoader from './SkeletonLoader';
import ErrorMessage from './ErrorMessage';

const HORIZONS = [7, 14, 30];

/**
 * @param {object} props
 * @param {{ forecast: Array<{date: string, predicted: number, lower: number, upper: number}>, metrics: object } | null} props.forecast
 * @param {Array<{date: string, quantity: number}>} props.history - Historical actuals
 * @param {boolean} props.loading
 * @param {string|null} props.error
 * @param {7|14|30} props.horizon - Currently selected forecast horizon
 * @param {function} props.onHorizonChange - Called with new horizon value when toggle is clicked
 * @param {function} [props.onRetry]
 */
export default function ForecastChart({
  forecast = null,
  history = [],
  loading = false,
  error = null,
  horizon = 14,
  onHorizonChange,
  onRetry,
}) {
  if (loading) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
        <SkeletonLoader rows={6} className="h-64" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
        <ErrorMessage
          message={`Failed to load forecast data. ${error}`}
          onRetry={onRetry}
        />
      </div>
    );
  }

  const forecastArray = forecast?.forecast ?? [];

  // Merge history and forecast into a single data array for Recharts.
  // Historical records have `actual`; forecast records have `predicted`, `lower`, `upper`.
  const chartData = [
    ...history.map((d) => ({
      date: d.date,
      actual: d.quantity,
      predicted: undefined,
      lower: undefined,
      upper: undefined,
    })),
    ...forecastArray.map((d) => ({
      date: d.date,
      actual: undefined,
      predicted: d.predicted,
      lower: d.lower,
      upper: d.upper,
    })),
  ];

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      {/* Header row: title + horizon toggle */}
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-base font-semibold text-gray-800">Demand Forecast</h2>

        {/* Horizon toggle buttons — Requirements 9.3, 9.4 */}
        <div
          className="flex rounded-lg border border-gray-200 overflow-hidden"
          role="group"
          aria-label="Forecast horizon"
        >
          {HORIZONS.map((h) => (
            <button
              key={h}
              onClick={() => onHorizonChange && onHorizonChange(h)}
              className={`px-3 py-1.5 text-xs font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-inset focus:ring-blue-500 ${
                horizon === h
                  ? 'bg-blue-600 text-white'
                  : 'bg-white text-gray-600 hover:bg-gray-50'
              }`}
              aria-pressed={horizon === h}
            >
              {h}d
            </button>
          ))}
        </div>
      </div>

      <ResponsiveContainer width="100%" height={320}>
        <ComposedChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 11 }}
            tickFormatter={(v) => v.slice(5)} // Show MM-DD
            interval="preserveStartEnd"
          />
          <YAxis tick={{ fontSize: 11 }} width={55} />
          <Tooltip content={<CustomTooltip />} />
          <Legend wrapperStyle={{ fontSize: 12 }} />

          {/* Confidence band — rendered as an Area with lower as baseline */}
          <Area
            type="monotone"
            dataKey="upper"
            stroke="none"
            fill="#bfdbfe"
            fillOpacity={0.5}
            name="Upper bound"
            legendType="none"
            connectNulls={false}
            activeDot={false}
            isAnimationActive={false}
          />
          <Area
            type="monotone"
            dataKey="lower"
            stroke="none"
            fill="#ffffff"
            fillOpacity={1}
            name="Lower bound"
            legendType="none"
            connectNulls={false}
            activeDot={false}
            isAnimationActive={false}
          />

          {/* Historical actuals — solid blue line */}
          <Line
            type="monotone"
            dataKey="actual"
            stroke="#2563eb"
            strokeWidth={2}
            dot={false}
            name="Actual"
            connectNulls={false}
          />

          {/* Forecast predicted — dashed orange line */}
          <Line
            type="monotone"
            dataKey="predicted"
            stroke="#f97316"
            strokeWidth={2}
            strokeDasharray="5 4"
            dot={false}
            name="Forecast"
            connectNulls={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload || payload.length === 0) return null;

  // Determine whether this is a historical or forecast point
  const actualEntry = payload.find((p) => p.dataKey === 'actual');
  const predictedEntry = payload.find((p) => p.dataKey === 'predicted');
  const upperEntry = payload.find((p) => p.dataKey === 'upper');
  const lowerEntry = payload.find((p) => p.dataKey === 'lower');

  const isHistorical = actualEntry && actualEntry.value != null;

  return (
    <div className="rounded-lg border border-gray-200 bg-white px-3 py-2 shadow-md text-xs">
      <p className="mb-1 font-semibold text-gray-700">{label}</p>
      {isHistorical ? (
        <p className="text-blue-600">
          Actual: <span className="font-medium">{Number(actualEntry.value).toFixed(0)}</span>
        </p>
      ) : (
        <>
          {predictedEntry && predictedEntry.value != null && (
            <p className="text-orange-500">
              Forecast: <span className="font-medium">{Number(predictedEntry.value).toFixed(0)}</span>
            </p>
          )}
          {lowerEntry && lowerEntry.value != null && (
            <p className="text-gray-500">
              Lower: <span className="font-medium">{Number(lowerEntry.value).toFixed(0)}</span>
            </p>
          )}
          {upperEntry && upperEntry.value != null && (
            <p className="text-gray-500">
              Upper: <span className="font-medium">{Number(upperEntry.value).toFixed(0)}</span>
            </p>
          )}
        </>
      )}
    </div>
  );
}

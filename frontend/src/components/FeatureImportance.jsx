/**
 * FeatureImportance — horizontal Recharts BarChart sorted descending by importance.
 *
 * Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6
 */

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Cell,
  LabelList,
  ResponsiveContainer,
} from 'recharts';
import SkeletonLoader from './SkeletonLoader';
import ErrorMessage from './ErrorMessage';

/**
 * @param {object} props
 * @param {{ features: Array<{name: string, importance: number}> } | null} props.importance
 * @param {boolean} props.loading
 * @param {string|null} props.error
 * @param {function} [props.onRetry]
 */
export default function FeatureImportance({
  importance = null,
  loading = false,
  error = null,
  onRetry,
}) {
  if (loading) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
        <SkeletonLoader rows={6} />
      </div>
    );
  }

  // Accept either an object with .features array or a plain array
  const features = Array.isArray(importance)
    ? importance
    : (importance?.features ?? []);

  if (error || features.length === 0) {
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
        <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-500">
          Feature Importance
        </p>
        <p className="mb-2 text-sm text-gray-500">What drove this forecast</p>
        <ErrorMessage
          message={
            error
              ? `Failed to load feature importance data. ${error}`
              : 'No feature importance data available for this product.'
          }
          onRetry={onRetry}
        />
      </div>
    );
  }

  // Sort descending by importance (Requirements 12.2)
  const sorted = [...features].sort((a, b) => b.importance - a.importance);

  // Recharts horizontal bar chart: layout="vertical" makes bars horizontal
  const barHeight = 32;
  const chartHeight = Math.max(sorted.length * barHeight + 40, 200);

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
        Feature Importance
      </p>
      {/* Subtitle — Requirements 12.4 */}
      <p className="mt-0.5 mb-4 text-sm text-gray-500">What drove this forecast</p>

      <ResponsiveContainer width="100%" height={chartHeight}>
        <BarChart
          data={sorted}
          layout="vertical"
          margin={{ top: 0, right: 80, left: 10, bottom: 0 }}
        >
          <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f0f0f0" />
          <XAxis
            type="number"
            tick={{ fontSize: 11 }}
            tickFormatter={(v) => v.toFixed(3)}
          />
          <YAxis
            type="category"
            dataKey="name"
            tick={{ fontSize: 11 }}
            width={110}
          />
          <Tooltip
            formatter={(value) => [value.toFixed(3), 'Importance']}
            cursor={{ fill: '#f3f4f6' }}
          />
          <Bar dataKey="importance" radius={[0, 4, 4, 0]}>
            {sorted.map((entry, index) => (
              <Cell
                key={`cell-${index}`}
                fill={entry.importance >= 0 ? '#3b82f6' : '#f87171'}
              />
            ))}
            {/* Label: importance to 3 decimal places — Requirements 12.3 */}
            <LabelList
              dataKey="importance"
              position="right"
              formatter={(v) => v.toFixed(3)}
              style={{ fontSize: 11, fill: '#6b7280' }}
            />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

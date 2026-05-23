import {
  ComposedChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import SkeletonLoader from './SkeletonLoader';
import ErrorMessage from './ErrorMessage';

// Fewer horizons — only practical options for a store manager
const HORIZONS = [7, 14, 30];

const FESTIVALS = [
  // 2023
  { date: '2023-01-14', name: 'Pongal' },
  { date: '2023-04-14', name: 'Tamil New Year' },
  { date: '2023-10-11', name: 'Ayudha Pooja' },
  { date: '2023-10-19', name: 'Diwali' },
  { date: '2023-10-31', name: 'Diwali' },
  // 2024
  { date: '2024-01-14', name: 'Pongal' },
  { date: '2024-04-14', name: 'Tamil New Year' },
  { date: '2024-10-11', name: 'Ayudha Pooja' },
  { date: '2024-10-19', name: 'Diwali' },
  { date: '2024-10-31', name: 'Diwali' },
  // 2025
  { date: '2025-01-14', name: 'Pongal' },
  { date: '2025-04-14', name: 'Tamil New Year' },
  { date: '2025-10-11', name: 'Ayudha Pooja' },
  { date: '2025-10-19', name: 'Diwali' },
  { date: '2025-10-31', name: 'Diwali' },
];

const parseDate = (dateStr) => {
  if (!dateStr) return new Date();
  const clean = String(dateStr).split(/[ T]/)[0];
  const parts = clean.split('-');
  if (parts.length === 3) {
    return new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]));
  }
  return new Date(dateStr);
};

export default function ForecastChart({
  forecast = null,
  history  = [],
  loading  = false,
  error    = null,
  horizon  = 14,
  onHorizonChange,
  onRetry,
  unitPrice  = 0.0,
  yAxisUnit  = 'quantity',
  onUnitChange,
}) {
  if (loading) {
    return (
      <div className="rounded-xl border border-white/10 bg-slate-900/40 p-5 shadow-2xl backdrop-blur-md">
        <SkeletonLoader rows={6} className="h-64" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-white/10 bg-slate-900/40 p-5 shadow-2xl backdrop-blur-md">
        <ErrorMessage
          message={`Failed to load forecast data. ${error}`}
          onRetry={onRetry}
        />
      </div>
    );
  }

  const forecastArray = forecast?.forecast ?? [];

  // Plain-English summary numbers
  let expectedDemand = 0;
  let expectedPeak   = 0;
  if (forecastArray.length > 0) {
    expectedDemand = forecastArray.reduce((sum, d) => sum + Math.max(0, Math.round(d.predicted)), 0);
    expectedPeak   = Math.max(...forecastArray.map((d) => Math.max(0, Math.round(d.predicted))));
  }

  const scaleFactor          = yAxisUnit === 'revenue' ? unitPrice : 1.0;
  const scaledExpectedDemand = expectedDemand * scaleFactor;
  const scaledExpectedPeak   = expectedPeak   * scaleFactor;

  const chartData = [
    ...history.map((d) => ({
      date:      d.date,
      actual:    Math.max(0, Math.round(d.quantity)) * scaleFactor,
      predicted: undefined,
    })),
    ...forecastArray.map((d) => ({
      date:      d.date,
      actual:    undefined,
      predicted: Math.max(0, Math.round(d.predicted)) * scaleFactor,
    })),
  ];

  // Connect the history line to the forecast line at the transition point
  if (history.length > 0 && forecastArray.length > 0) {
    chartData[history.length - 1].predicted =
      Math.max(0, Math.round(history[history.length - 1].quantity)) * scaleFactor;
  }

  // Identify festivals that appear in the chart range
  const activeFestivals = FESTIVALS.filter((f) =>
    chartData.some((d) => d.date === f.date)
  );

  const formatSummaryVal = (val) =>
    yAxisUnit === 'revenue'
      ? `₹${Math.round(val).toLocaleString()}`
      : `${Math.round(val).toLocaleString()} units`;

  const formatYAxis = (v) =>
    yAxisUnit === 'revenue'
      ? `₹${Math.round(v / 1000)}k`
      : Math.round(v).toLocaleString();

  return (
    <div className="rounded-xl border border-white/10 bg-slate-900/40 p-5 shadow-2xl backdrop-blur-md">

      {/* ---------------------------------------------------------------- */}
      {/* Header — plain-English summary is primary content                */}
      {/* ---------------------------------------------------------------- */}
      <div className="mb-4">
        <h2 className="text-base font-bold text-white">Sales Trend &amp; Forecast</h2>

        {forecastArray.length > 0 && (
          <p className="mt-2 rounded-lg bg-indigo-950/40 border border-indigo-500/20 px-4 py-2.5 text-sm text-slate-300 leading-relaxed">
            Based on past sales patterns, you are expected to sell{' '}
            <span className="font-bold text-indigo-300">{formatSummaryVal(scaledExpectedDemand)}</span>{' '}
            over the next {horizon} days — with a possible single-day peak of{' '}
            <span className="font-semibold text-slate-200">{formatSummaryVal(scaledExpectedPeak)}</span>.
            {activeFestivals.length > 0 && (
              <>
                {' '}The dotted lines mark upcoming festivals where sales typically spike.
              </>
            )}
          </p>
        )}
      </div>

      {/* ---------------------------------------------------------------- */}
      {/* Controls — tucked below the summary, not above it                */}
      {/* ---------------------------------------------------------------- */}
      <div className="mb-4 flex flex-wrap items-center gap-2 border-b border-white/5 pb-4">
        <p className="text-xs text-slate-500 mr-1">Show:</p>

        {/* Unit toggle */}
        <div className="flex rounded-lg border border-white/10 overflow-hidden" role="group" aria-label="Toggle units">
          {[
            { id: 'quantity', label: 'Units Sold' },
            { id: 'revenue',  label: 'Revenue (₹)' },
          ].map(({ id, label }) => (
            <button
              key={id}
              onClick={() => onUnitChange && onUnitChange(id)}
              className={`px-3 py-1.5 text-xs font-semibold transition-colors focus:outline-none ${
                yAxisUnit === id
                  ? 'bg-indigo-600 text-white'
                  : 'bg-slate-900/50 text-slate-400 hover:text-slate-200'
              }`}
              aria-pressed={yAxisUnit === id}
            >
              {label}
            </button>
          ))}
        </div>

        <p className="text-xs text-slate-500 ml-2 mr-1">Forecast:</p>

        {/* Horizon toggle */}
        <div className="flex rounded-lg border border-white/10 overflow-hidden" role="group" aria-label="Forecast horizon">
          {HORIZONS.map((h) => (
            <button
              key={h}
              onClick={() => onHorizonChange && onHorizonChange(h)}
              className={`px-3 py-1.5 text-xs font-semibold transition-colors focus:outline-none ${
                horizon === h
                  ? 'bg-indigo-600 text-white'
                  : 'bg-slate-900/50 text-slate-400 hover:text-slate-200'
              }`}
              aria-pressed={horizon === h}
            >
              {h} days
            </button>
          ))}
        </div>
      </div>

      {/* ---------------------------------------------------------------- */}
      {/* Chart                                                             */}
      {/* ---------------------------------------------------------------- */}
      <ResponsiveContainer width="100%" height={300}>
        <ComposedChart data={chartData} margin={{ top: 12, right: 20, left: 10, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 11, fill: '#94a3b8' }}
            tickFormatter={(v) =>
              parseDate(v).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
            }
            interval="preserveStartEnd"
            tickLine={false}
            axisLine={false}
          />
          <YAxis
            tick={{ fontSize: 11, fill: '#94a3b8' }}
            width={yAxisUnit === 'revenue' ? 60 : 50}
            tickLine={false}
            axisLine={false}
            tickFormatter={formatYAxis}
          />
          <Tooltip content={<CustomTooltip yAxisUnit={yAxisUnit} />} />
          <Legend
            wrapperStyle={{ fontSize: 12, paddingTop: '12px', color: '#94a3b8' }}
            iconType="circle"
          />

          {/* Festival vertical lines */}
          {activeFestivals.map((f, idx) => (
            <ReferenceLine
              key={idx}
              x={f.date}
              stroke="#f43f5e"
              strokeDasharray="4 4"
              strokeWidth={1.5}
              label={{
                value: f.name,
                position: 'top',
                fill: '#f43f5e',
                fontSize: 10,
                fontWeight: 'bold',
              }}
            />
          ))}

          {/* Historical sales — muted grey */}
          <Line
            type="monotone"
            dataKey="actual"
            stroke="#64748b"
            strokeWidth={2.5}
            dot={false}
            name="Past Sales"
            connectNulls={true}
          />

          {/* Forecast — prominent indigo */}
          <Line
            type="monotone"
            dataKey="predicted"
            stroke="#6366f1"
            strokeWidth={3.5}
            dot={false}
            name="Expected Sales"
            connectNulls={true}
          />
        </ComposedChart>
      </ResponsiveContainer>

      {/* ---------------------------------------------------------------- */}
      {/* Legend explanation below chart                                    */}
      {/* ---------------------------------------------------------------- */}
      <div className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-xs text-slate-500">
        <span><span className="inline-block w-3 h-0.5 bg-slate-500 mr-1 align-middle" /> Grey line = what actually sold in the past</span>
        <span><span className="inline-block w-3 h-0.5 bg-indigo-500 mr-1 align-middle" /> Blue line = what we predict you will sell</span>
        {activeFestivals.length > 0 && (
          <span><span className="inline-block w-px h-3 border-l-2 border-dashed border-rose-400 mr-1 align-middle" /> Red dotted lines = festival dates (expect higher sales)</span>
        )}
      </div>
    </div>
  );
}

function CustomTooltip({ active, payload, label, yAxisUnit }) {
  if (!active || !payload || payload.length === 0) return null;

  const actualEntry    = payload.find((p) => p.dataKey === 'actual');
  const predictedEntry = payload.find((p) => p.dataKey === 'predicted');
  const isHistorical   = actualEntry && actualEntry.value != null;

  const formatVal = (val) =>
    yAxisUnit === 'revenue'
      ? `₹${Number(val).toLocaleString(undefined, { maximumFractionDigits: 0 })}`
      : `${Number(val).toLocaleString(undefined, { maximumFractionDigits: 0 })} units`;

  return (
    <div className="rounded-xl border border-white/10 bg-slate-950/90 px-4 py-3 shadow-2xl text-sm backdrop-blur-md text-slate-100">
      <p className="mb-2 font-bold text-slate-200 border-b border-white/10 pb-1">
        {parseDate(label).toLocaleDateString(undefined, {
          weekday: 'long', month: 'short', day: 'numeric',
        })}
      </p>
      {isHistorical ? (
        <p className="text-slate-300 flex justify-between gap-4">
          <span>Sold:</span>
          <span className="font-bold text-slate-100">{formatVal(actualEntry.value)}</span>
        </p>
      ) : (
        predictedEntry && predictedEntry.value != null && (
          <p className="text-indigo-300 flex justify-between gap-4">
            <span>Expected:</span>
            <span className="font-bold text-indigo-200">{formatVal(predictedEntry.value)}</span>
          </p>
        )
      )}
    </div>
  );
}

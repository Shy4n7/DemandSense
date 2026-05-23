import SkeletonLoader from './SkeletonLoader';

/**
 * MetricsCards — three clear, plain-English insight cards for the selected product.
 *
 * Cards answer:
 *   1. How much will I sell? (Expected Sales)
 *   2. Do I need to order more? (Stock Status from inventory API)
 *   3. How many unusual things happened? (Alerts)
 */
export default function MetricsCards({
  forecast        = null,
  anomalies       = null,
  inventory       = null,          // from /api/inventory
  loadingForecast = false,
  loadingAnomalies= false,
  loadingInventory= false,
  errorForecast   = null,
  errorAnomalies  = null,
  errorInventory  = null,
  unitPrice       = 0.0,
  yAxisUnit       = 'quantity',
}) {
  const totalAnomalies = anomalies?.total_anomalies ?? null;

  // Expected demand for the full horizon
  let expectedDemand = null;
  if (forecast?.forecast) {
    expectedDemand = forecast.forecast.reduce((sum, d) => sum + Math.max(0, Math.round(d.predicted)), 0);
  }

  const scaleFactor          = yAxisUnit === 'revenue' ? unitPrice : 1.0;
  const scaledExpectedDemand = expectedDemand != null ? expectedDemand * scaleFactor : null;

  const formatVal = (val) => {
    if (val == null) return null;
    return yAxisUnit === 'revenue'
      ? `₹${Math.round(val).toLocaleString()}`
      : `${Math.round(val).toLocaleString()} units`;
  };

  // Stock status from /api/inventory
  const status          = inventory?.status ?? null;       // "SUFFICIENT" | "REORDER NOW" | "CRITICAL"
  const suggestedOrder  = inventory?.suggested_order ?? null;
  const reorderPoint    = inventory?.reorder_point ?? null;
  const currentStock    = inventory?.current_stock ?? null;

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">

      {/* ---- Card 1: Expected sales ---- */}
      <MetricCard
        label="Expected Sales"
        loading={loadingForecast}
        error={errorForecast}
        highlight={false}
      >
        {scaledExpectedDemand != null ? (
          <>
            <p className="text-3xl font-black text-white">{formatVal(scaledExpectedDemand)}</p>
            <p className="mt-2 text-xs text-slate-400 leading-snug">
              This is how much we predict you will sell in the selected period. Use this to decide whether to order more stock.
            </p>
          </>
        ) : (
          <p className="text-3xl font-black text-slate-500">N/A</p>
        )}
      </MetricCard>

      {/* ---- Card 2: Stock status ---- */}
      <MetricCard
        label="Stock Status"
        loading={loadingInventory}
        error={errorInventory}
        highlight={status === 'CRITICAL' || status === 'REORDER NOW'}
        highlightColor={status === 'CRITICAL' ? 'rose' : status === 'REORDER NOW' ? 'amber' : 'emerald'}
      >
        {status != null ? (
          <>
            <StatusBadge status={status} />
            {suggestedOrder != null && suggestedOrder > 0 ? (
              <p className="mt-2 text-xs text-slate-400 leading-snug">
                Order <span className="font-bold text-slate-200">{Math.round(suggestedOrder)} units</span> to get back to a safe level.
                {reorderPoint != null && (
                  <> Trigger reorder when stock falls below <span className="font-bold text-slate-200">{Math.round(reorderPoint)}</span>.</>
                )}
              </p>
            ) : (
              <p className="mt-2 text-xs text-slate-400 leading-snug">
                {currentStock != null
                  ? `You have ${Math.round(currentStock)} units on hand. No order needed right now.`
                  : 'Enter your stock level below to get restock advice.'}
              </p>
            )}
          </>
        ) : (
          <p className="mt-2 text-xs text-slate-400 leading-snug">
            Enter your stock level below to get a restock recommendation.
          </p>
        )}
      </MetricCard>

      {/* ---- Card 3: Alerts ---- */}
      <MetricCard
        label="Price &amp; Stock Alerts"
        loading={loadingAnomalies}
        error={errorAnomalies}
        highlight={totalAnomalies != null && totalAnomalies > 0}
        highlightColor="amber"
      >
        {totalAnomalies != null ? (
          <>
            <p className={`text-3xl font-black ${totalAnomalies > 0 ? 'text-amber-300' : 'text-emerald-300'}`}>
              {totalAnomalies === 0 ? 'All Clear' : `${totalAnomalies} Alert${totalAnomalies > 1 ? 's' : ''}`}
            </p>
            <p className="mt-2 text-xs text-slate-400 leading-snug">
              {totalAnomalies === 0
                ? 'No unusual pricing or demand changes were detected for this product.'
                : 'Unusual pricing or demand patterns were detected. Scroll down to review them.'}
            </p>
          </>
        ) : (
          <p className="text-3xl font-black text-slate-500">N/A</p>
        )}
      </MetricCard>

    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* StatusBadge — big coloured pill for CRITICAL / REORDER NOW / SUFFICIENT    */
/* -------------------------------------------------------------------------- */
function StatusBadge({ status }) {
  const map = {
    CRITICAL:    { text: 'CRITICAL',     cls: 'bg-rose-600/30 text-rose-200 border-rose-500/40' },
    'REORDER NOW': { text: 'ORDER SOON', cls: 'bg-amber-600/30 text-amber-200 border-amber-500/40' },
    SUFFICIENT:  { text: 'STOCK OK',     cls: 'bg-emerald-600/30 text-emerald-200 border-emerald-500/40' },
  };
  const { text, cls } = map[status] ?? { text: status, cls: 'bg-slate-700 text-slate-300 border-slate-600' };

  return (
    <span className={`inline-block rounded-lg border px-3 py-1 text-base font-black uppercase tracking-widest ${cls}`}>
      {text}
    </span>
  );
}

/* -------------------------------------------------------------------------- */
/* MetricCard shell                                                            */
/* -------------------------------------------------------------------------- */
function MetricCard({ label, children, loading, error, highlight, highlightColor = 'indigo' }) {
  const colorMap = {
    rose:    'border-rose-500/20 bg-rose-950/20',
    amber:   'border-amber-500/20 bg-amber-950/10',
    emerald: 'border-emerald-500/20 bg-emerald-950/10',
    indigo:  'border-indigo-500/30 bg-indigo-950/20',
  };
  const cardClass = highlight
    ? colorMap[highlightColor]
    : 'border-white/10 bg-slate-900/40';

  return (
    <div className={`rounded-xl border p-5 shadow-sm backdrop-blur-md ${cardClass}`}>
      <p className="text-xs font-semibold uppercase tracking-widest text-slate-400">{label}</p>

      {loading ? (
        <div className="mt-3" role="status" aria-label="Loading">
          <SkeletonLoader rows={2} />
        </div>
      ) : error ? (
        <p className="mt-3 text-sm font-medium text-red-400" role="alert">{error}</p>
      ) : (
        <div className="mt-3">{children}</div>
      )}
    </div>
  );
}

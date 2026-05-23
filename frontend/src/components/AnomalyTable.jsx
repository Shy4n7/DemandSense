import { useState } from 'react';
import SkeletonLoader from './SkeletonLoader';
import ErrorMessage from './ErrorMessage';

const FILTERS = [
  { label: 'All',           value: 'all' },
  { label: 'Demand Spike',  value: 'demand_spike' },
  { label: 'Price Anomaly', value: 'price_anomaly' },
  { label: 'Stockout Signal',value: 'stockout_signal' },
];

export default function AnomalyTable({
  anomalies = null,
  loading   = false,
  error     = null,
  onRetry,
}) {
  const [activeFilter, setActiveFilter] = useState('all');

  if (loading) {
    return (
      <div className="rounded-xl border border-white/10 bg-slate-900/40 p-5 shadow-2xl backdrop-blur-md">
        <SkeletonLoader rows={5} />
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl border border-white/10 bg-slate-900/40 p-5 shadow-2xl backdrop-blur-md">
        <ErrorMessage
          message={`Failed to load anomaly data. ${error}`}
          onRetry={onRetry}
        />
      </div>
    );
  }

  const anomalyRows = Array.isArray(anomalies)
    ? anomalies
    : (anomalies?.anomalies ?? []);

  // Only show anomalies from the last 30 days (assume "today" is the end of the dataset, 2024-12-31)
  const recentAnomalyRows = anomalyRows.filter((a) => {
    const anomalyDate = new Date(a.date);
    const cutoffDate = new Date('2024-12-01');
    return anomalyDate >= cutoffDate;
  });

  const filtered = (
    activeFilter === 'all'
      ? recentAnomalyRows
      : recentAnomalyRows.filter((a) => a.reason === activeFilter)
  ).sort((a, b) => {
    // Sort: most urgent first (lowest score = most anomalous), then by date desc
    if (a.anomaly_score !== b.anomaly_score) return a.anomaly_score - b.anomaly_score;
    return new Date(b.date) - new Date(a.date);
  });

  // Split into "Act Now" and "Keep an Eye On"
  const actNow   = filtered.filter((r) => r.anomaly_score < -0.1);
  const watchList= filtered.filter((r) => r.anomaly_score >= -0.1);

  return (
    <div className="rounded-xl border border-white/10 bg-slate-900/40 p-5 shadow-2xl backdrop-blur-md">

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-white/10 pb-4 mb-4">
        <div>
          <h2 className="text-base font-bold text-white">Recent Activity Alerts</h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Unusual activity in the last 30 days — review and act where needed.
          </p>
        </div>

        {/* Filter chips */}
        <div className="flex flex-wrap gap-2" role="group" aria-label="Filter anomalies">
          {FILTERS.map((f) => (
            <button
              key={f.value}
              onClick={() => setActiveFilter(f.value)}
              className={`rounded-full px-3 py-1 text-xs font-semibold transition-colors focus:outline-none ${
                activeFilter === f.value
                  ? 'bg-indigo-600 text-white'
                  : 'bg-white/5 text-slate-400 hover:bg-white/10 hover:text-slate-200 border border-white/5'
              }`}
              aria-pressed={activeFilter === f.value}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {/* Empty state */}
      {filtered.length === 0 && (
        <div className="py-10 text-center text-sm text-slate-400">
          No anomalies detected for this product.
        </div>
      )}

      {/* Act Now group */}
      {actNow.length > 0 && (
        <AlertGroup
          title="Act Now"
          titleColor="text-rose-400"
          description="These events are the most unusual and may affect your sales or cash flow."
          rows={actNow}
        />
      )}

      {/* Watch List group */}
      {watchList.length > 0 && (
        <AlertGroup
          title="Keep an Eye On"
          titleColor="text-amber-400"
          description="These events are slightly unusual. No immediate action needed, but worth knowing about."
          rows={watchList}
          className={actNow.length > 0 ? 'mt-5 pt-5 border-t border-white/5' : ''}
        />
      )}
    </div>
  );
}

/* ---------------------------------------------------------------------- */
/* AlertGroup — a labelled group of anomaly cards                          */
/* ---------------------------------------------------------------------- */
function AlertGroup({ title, titleColor, description, rows, className = '' }) {
  return (
    <div className={className}>
      <div className="flex items-center gap-2 mb-2">
        <p className={`text-xs font-bold uppercase tracking-widest ${titleColor}`}>{title}</p>
        <span className="text-xs text-slate-500">— {description}</span>
      </div>
      <div className="flex flex-col gap-2">
        {rows.map((row, idx) => (
          <AnomalyCard key={`${row.date}-${idx}`} row={row} />
        ))}
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------------- */
/* AnomalyCard                                                             */
/* ---------------------------------------------------------------------- */
function AnomalyCard({ row }) {
  const score   = row.anomaly_score;
  const dateStr = new Date(row.date).toLocaleDateString(undefined, {
    weekday: 'short', month: 'short', day: 'numeric',
  });

  const isCritical= score < -0.1;
  const isWarning = score >= -0.1 && score <= 0.0;

  const borderClass = isCritical ? 'border-red-500/20'   : isWarning ? 'border-amber-500/20' : 'border-white/10';
  const bgClass     = isCritical ? 'bg-red-950/20'        : isWarning ? 'bg-amber-950/20'     : 'bg-slate-900/30';

  return (
    <div
      data-testid={`anomaly-card-${row.date}`}
      className={`anomaly-card rounded-xl border p-4 shadow-sm ${borderClass} ${bgClass} transition-shadow hover:shadow-md`}
    >
      <div className="flex items-start justify-between gap-2 mb-2">
        <div>
          <ReasonBadge reason={row.reason} />
          <p className="mt-1 text-xs text-slate-400">{dateStr}</p>
        </div>
        {isCritical && (
          <span className="shrink-0 rounded-full border border-rose-700 bg-rose-600 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-white shadow-sm">
            Action Needed
          </span>
        )}
        {isWarning && !isCritical && (
          <span className="shrink-0 rounded-full border border-amber-700 bg-amber-600 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-white shadow-sm">
            Monitor
          </span>
        )}
      </div>

      {/* Plain-English explanation — the most important part */}
      <div className="rounded-lg bg-slate-950/40 border border-white/5 px-3 py-2.5 text-sm text-slate-300">
        <AnomalyExplanation row={row} />
      </div>

      {/* Supporting numbers */}
      <div className="mt-3 flex gap-4 text-xs text-slate-400">
        <span>Units sold: <span className="font-semibold text-slate-200">{row.quantity?.toLocaleString() ?? 0}</span></span>
        {row.unit_price != null && (
          <span>Price: <span className="font-semibold text-slate-200">₹{row.unit_price.toFixed(2)}</span></span>
        )}
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------------- */
/* AnomalyExplanation — what happened and what to do                       */
/* ---------------------------------------------------------------------- */
function AnomalyExplanation({ row }) {
  let what = '';
  let action = '';

  switch (row.reason) {
    case 'demand_spike':
      what   = `Sales were unusually high (${row.quantity?.toLocaleString()} units on this day).`;
      action = 'Consider ordering more stock so you are prepared if this happens again.';
      break;
    case 'price_anomaly':
      what   = `The selling price changed unexpectedly to ₹${row.unit_price?.toFixed(2)}.`;
      action = 'Please check whether this price is correct in your billing system.';
      break;
    case 'stockout_signal':
      what   = `Zero sales were recorded on this day.`;
      action = 'Check your shelves — the item may have run out of stock.';
      break;
    case 'isolation_forest':
      what   = `Our AI detected an unusual sales pattern on this day.`;
      action = 'No urgent action needed, but worth reviewing if this repeats.';
      break;
    default:
      what   = `Unusual activity was recorded on this day.`;
      action = 'Review the day\'s transactions for any issues.';
  }

  return (
    <p className="font-medium leading-snug">
      {what}{' '}
      <span className="text-slate-400">{action}</span>
    </p>
  );
}

/* ---------------------------------------------------------------------- */
/* ReasonBadge                                                             */
/* ---------------------------------------------------------------------- */
function ReasonBadge({ reason }) {
  const styles = {
    demand_spike:     'bg-emerald-950/40 text-emerald-400 border border-emerald-500/20',
    price_anomaly:    'bg-purple-950/40  text-purple-400  border border-purple-500/20',
    stockout_signal:  'bg-rose-950/40    text-rose-400    border border-rose-500/20',
    isolation_forest: 'bg-amber-950/40   text-amber-400   border border-amber-500/20',
  };
  const labels = {
    demand_spike:     'Demand Spike',
    price_anomaly:    'Price Anomaly',
    stockout_signal:  'Stockout Signal',
    isolation_forest: 'Review Needed',
  };

  const cls   = styles[reason] || 'bg-slate-800 text-slate-400 border border-slate-700/55';
  const label = labels[reason] || reason;

  return (
    <span className={`inline-block rounded-full px-2.5 py-1 text-xs font-bold ${cls}`}>
      {label}
    </span>
  );
}

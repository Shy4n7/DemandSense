import React from 'react';

export default function GlobalOverview({ products = [], onSelectProduct }) {
  // Separate products into urgent vs normal
  const criticalProducts = products.filter((p) => p.stockout_warning);
  const anomalyProducts  = products.filter((p) => (p.anomaly_count || 0) > 0 && !p.stockout_warning);
  const healthyProducts  = products.filter((p) => !p.stockout_warning && (p.anomaly_count || 0) === 0);

  const totalAlerts = criticalProducts.length + anomalyProducts.length;

  return (
    <div className="space-y-6">

      {/* ------------------------------------------------------------------ */}
      {/* TODAY AT A GLANCE — top banner                                      */}
      {/* ------------------------------------------------------------------ */}
      <div className="rounded-xl border border-white/10 bg-slate-900/50 p-5 shadow-2xl backdrop-blur-md">
        <p className="text-xs font-semibold uppercase tracking-widest text-slate-400 mb-4">
          Today at a Glance
        </p>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">

          {/* Action needed */}
          <div className={`rounded-lg p-4 border ${
            totalAlerts > 0
              ? 'border-rose-500/30 bg-rose-950/20'
              : 'border-emerald-500/30 bg-emerald-950/10'
          }`}>
            <p className={`text-2xl font-black ${totalAlerts > 0 ? 'text-rose-300' : 'text-emerald-300'}`}>
              {totalAlerts === 0 ? 'All Good' : `${totalAlerts} ${totalAlerts === 1 ? 'item' : 'items'} need action`}
            </p>
            <p className="mt-1 text-xs text-slate-400">
              {totalAlerts === 0
                ? 'No urgent issues across your products today.'
                : 'Scroll down to see what needs your attention.'}
            </p>
          </div>

          {/* Products tracked */}
          <div className="rounded-lg p-4 border border-white/10 bg-white/5">
            <p className="text-2xl font-black text-white">{products.length}</p>
            <p className="mt-1 text-xs text-slate-400">
              Products being tracked by DemandSense.
            </p>
          </div>

          {/* Healthy products */}
          <div className="rounded-lg p-4 border border-white/10 bg-white/5">
            <p className="text-2xl font-black text-white">{healthyProducts.length}</p>
            <p className="mt-1 text-xs text-slate-400">
              Products with no alerts and normal sales patterns.
            </p>
          </div>

        </div>
      </div>

      {/* ------------------------------------------------------------------ */}
      {/* ACTION CHECKLIST — only shown if there are alerts                   */}
      {/* ------------------------------------------------------------------ */}
      {totalAlerts > 0 && (
        <div className="rounded-xl border border-white/10 bg-slate-900/50 p-5 shadow-2xl backdrop-blur-md">
          <p className="text-xs font-semibold uppercase tracking-widest text-slate-400 mb-4">
            What You Need to Do Today
          </p>
          <div className="space-y-2">
            {/* Critical — zero sales for 14 days */}
            {criticalProducts.map((p) => (
              <ActionItem
                key={`crit-${p.product_id}`}
                severity="critical"
                onClick={() => onSelectProduct(p.product_id)}
              >
                <span className="font-bold text-slate-100">{p.description}</span>
                <span className="text-slate-400 ml-1">
                  — no sales recorded in 14 days. Check if shelves are empty.
                </span>
              </ActionItem>
            ))}

            {/* Anomaly — price or demand spike */}
            {anomalyProducts.map((p) => (
              <ActionItem
                key={`anom-${p.product_id}`}
                severity="warning"
                onClick={() => onSelectProduct(p.product_id)}
              >
                <span className="font-bold text-slate-100">{p.description}</span>
                <span className="text-slate-400 ml-1">
                  — {p.anomaly_count} unusual event{p.anomaly_count > 1 ? 's' : ''} found. Tap to review.
                </span>
              </ActionItem>
            ))}
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------------ */}
      {/* PRODUCT GRID — traffic-light status for every product               */}
      {/* ------------------------------------------------------------------ */}
      <div className="rounded-xl border border-white/10 bg-slate-900/50 p-5 shadow-2xl backdrop-blur-md">
        <p className="text-xs font-semibold uppercase tracking-widest text-slate-400 mb-4">
          All Products — click any to view its forecast and alerts
        </p>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {products
            .sort((a, b) => {
              // Sort: critical first, then anomaly, then healthy
              const score = (p) => (p.stockout_warning ? 2 : (p.anomaly_count || 0) > 0 ? 1 : 0);
              return score(b) - score(a);
            })
            .map((p) => (
              <ProductCard key={p.product_id} product={p} onClick={() => onSelectProduct(p.product_id)} />
            ))}
        </div>
      </div>

    </div>
  );
}

/* ---------------------------------------------------------------------- */
/* ActionItem — a single row in the "what to do today" checklist           */
/* ---------------------------------------------------------------------- */
function ActionItem({ severity, children, onClick }) {
  const styles = {
    critical: 'border-rose-500/30 bg-rose-950/20 hover:bg-rose-950/30',
    warning:  'border-amber-500/30 bg-amber-950/10 hover:bg-amber-950/20',
  };
  const badgeStyles = {
    critical: 'bg-rose-500/20 text-rose-300 border-rose-500/40',
    warning:  'bg-amber-500/20 text-amber-300 border-amber-500/40',
  };
  const badgeText = {
    critical: 'Act Now',
    warning:  'Review',
  };

  return (
    <button
      onClick={onClick}
      className={`w-full text-left flex items-start gap-3 rounded-lg border p-3 cursor-pointer transition-all duration-200 ${styles[severity]}`}
    >
      <span className={`mt-0.5 shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide ${badgeStyles[severity]}`}>
        {badgeText[severity]}
      </span>
      <span className="text-sm leading-snug">{children}</span>
      <svg className="ml-auto mt-1 h-3.5 w-3.5 shrink-0 text-slate-500" viewBox="0 0 20 20" fill="currentColor">
        <path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clipRule="evenodd" />
      </svg>
    </button>
  );
}

/* ---------------------------------------------------------------------- */
/* ProductCard — a single product in the grid with traffic-light status    */
/* ---------------------------------------------------------------------- */
function ProductCard({ product: p, onClick }) {
  const isCritical = p.stockout_warning;
  const isWarning  = !isCritical && (p.anomaly_count || 0) > 0;
  const isHealthy  = !isCritical && !isWarning;

  const dotColor = isCritical ? 'bg-rose-400'   : isWarning ? 'bg-amber-400'  : 'bg-emerald-400';
  const statusText = isCritical ? 'No recent sales' : isWarning ? `${p.anomaly_count} alert${p.anomaly_count > 1 ? 's' : ''}` : 'Normal';
  const statusColor = isCritical ? 'text-rose-400' : isWarning ? 'text-amber-400' : 'text-emerald-400';

  return (
    <button
      onClick={onClick}
      className="group w-full text-left rounded-lg border border-white/10 bg-white/5 p-4 transition-all duration-200 hover:border-white/20 hover:bg-white/10"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-slate-100 leading-snug truncate">{p.description}</p>
          <p className="mt-0.5 text-xs text-slate-500 font-mono">{p.product_id}</p>
        </div>
        <div className={`mt-1 h-2.5 w-2.5 shrink-0 rounded-full ${dotColor}`} />
      </div>
      <div className="mt-3 flex items-center justify-between">
        <p className={`text-xs font-semibold ${statusColor}`}>{statusText}</p>
        <svg className="h-3.5 w-3.5 text-slate-600 transition-transform duration-200 group-hover:text-slate-400 group-hover:translate-x-0.5" viewBox="0 0 20 20" fill="currentColor">
          <path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clipRule="evenodd" />
        </svg>
      </div>
    </button>
  );
}

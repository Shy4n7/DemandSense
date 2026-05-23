import { useState } from 'react';
import SkeletonLoader from './SkeletonLoader';

/**
 * InventoryPlanner — lets the retailer enter their current stock and supplier
 * lead time, then shows clear restock recommendations from /api/inventory.
 */
export default function InventoryPlanner({
  currentStock,
  leadTime,
  serviceLevel,
  onCurrentStockChange,
  onLeadTimeChange,
  onServiceLevelChange,
  inventory       = null,
  loadingInventory= false,
  errorInventory  = null,
}) {
  return (
    <div className="rounded-xl border border-white/10 bg-slate-900/40 p-5 shadow-2xl backdrop-blur-md">
      <div className="mb-4">
        <h2 className="text-base font-bold text-white">Restock Planner</h2>
        <p className="mt-1 text-xs text-slate-400 leading-snug">
          Tell us your current stock and how long your supplier takes to deliver — we will instantly calculate whether you need to reorder and exactly how much to order.
        </p>
      </div>

      {/* ---------------------------------------------------------------- */}
      {/* Inputs                                                            */}
      {/* ---------------------------------------------------------------- */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3 mb-5">

        {/* Current stock */}
        <div>
          <label className="block text-xs font-semibold text-slate-300 mb-1.5" htmlFor="inp-current-stock">
            Units in Stock Right Now
          </label>
          <input
            id="inp-current-stock"
            type="number"
            min={0}
            step={1}
            value={currentStock}
            onChange={(e) => onCurrentStockChange(Math.max(0, Number(e.target.value)))}
            className="w-full rounded-lg border border-white/10 bg-slate-800/50 px-3 py-2 text-sm text-slate-100 placeholder-slate-500 outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all duration-200"
          />
          <p className="mt-1 text-xs text-slate-500">How many units are on your shelves right now?</p>
        </div>

        {/* Lead time */}
        <div>
          <label className="block text-xs font-semibold text-slate-300 mb-1.5" htmlFor="inp-lead-time">
            Days to Receive Delivery
          </label>
          <input
            id="inp-lead-time"
            type="number"
            min={1}
            max={90}
            step={1}
            value={leadTime}
            onChange={(e) => onLeadTimeChange(Math.min(90, Math.max(1, Number(e.target.value))))}
            className="w-full rounded-lg border border-white/10 bg-slate-800/50 px-3 py-2 text-sm text-slate-100 placeholder-slate-500 outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all duration-200"
          />
          <p className="mt-1 text-xs text-slate-500">How many days from ordering to delivery?</p>
        </div>

        {/* Service level */}
        <div>
          <label className="block text-xs font-semibold text-slate-300 mb-1.5" htmlFor="inp-service-level">
            Stock Safety Level
          </label>
          <select
            id="inp-service-level"
            value={serviceLevel}
            onChange={(e) => onServiceLevelChange(Number(e.target.value))}
            className="w-full rounded-lg border border-white/10 bg-slate-800/50 px-3 py-2 text-sm text-slate-100 outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition-all duration-200"
          >
            <option value={0.9}>Normal (90%)</option>
            <option value={0.95}>Standard (95%)</option>
            <option value={0.99}>Very Safe (99%)</option>
          </select>
          <p className="mt-1 text-xs text-slate-500">Higher = more buffer stock kept in reserve.</p>
        </div>
      </div>

      {/* ---------------------------------------------------------------- */}
      {/* Results                                                           */}
      {/* ---------------------------------------------------------------- */}
      {loadingInventory && (
        <div role="status" aria-label="Loading">
          <SkeletonLoader rows={3} />
        </div>
      )}

      {errorInventory && !loadingInventory && (
        <p className="text-sm text-red-400 rounded-lg border border-red-500/20 bg-red-950/20 p-3" role="alert">
          {errorInventory}
        </p>
      )}

      {inventory && !loadingInventory && !errorInventory && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">

          <ResultCard
            label="Order This Many Units"
            value={inventory.suggested_order > 0 ? `${Math.round(inventory.suggested_order)} units` : 'No order needed'}
            subtext={
              inventory.suggested_order > 0
                ? 'Order this quantity to bring your stock back to a safe level.'
                : 'Your current stock is sufficient for the expected demand.'
            }
            highlight={inventory.suggested_order > 0}
            highlightColor={inventory.status === 'CRITICAL' ? 'rose' : 'amber'}
          />

          <ResultCard
            label="Order When Stock Drops Below"
            value={`${Math.round(inventory.reorder_point)} units`}
            subtext="This is your reorder trigger point — do not let stock fall below this level."
          />

          <ResultCard
            label="Safety Buffer to Keep"
            value={`${Math.round(inventory.safety_stock)} units`}
            subtext="Extra stock kept in reserve to handle unexpected spikes in sales."
          />

          <ResultCard
            label="Sales During Delivery Window"
            value={`${Math.round(inventory.forecasted_demand)} units`}
            subtext={`Expected sales in the next ${leadTime} day${leadTime !== 1 ? 's' : ''} while waiting for your delivery.`}
          />
        </div>
      )}
    </div>
  );
}

/* ---------------------------------------------------------------------- */
/* ResultCard — a single result metric with explanation                    */
/* ---------------------------------------------------------------------- */
function ResultCard({ label, value, subtext, highlight = false, highlightColor = 'indigo' }) {
  const colorMap = {
    rose:   'border-rose-500/30 bg-rose-950/20',
    amber:  'border-amber-500/30 bg-amber-950/10',
    emerald:'border-emerald-500/30 bg-emerald-950/10',
    indigo: 'border-white/10 bg-white/5',
  };
  const valueColorMap = {
    rose:   'text-rose-200',
    amber:  'text-amber-200',
    emerald:'text-emerald-200',
    indigo: 'text-white',
  };

  const cardCls  = highlight ? colorMap[highlightColor]   : colorMap.indigo;
  const valueCls = highlight ? valueColorMap[highlightColor] : valueColorMap.indigo;

  return (
    <div className={`rounded-lg border p-4 ${cardCls}`}>
      <p className="text-xs font-semibold uppercase tracking-widest text-slate-400 mb-2">{label}</p>
      <p className={`text-xl font-black ${valueCls}`}>{value}</p>
      <p className="mt-1.5 text-xs text-slate-400 leading-snug">{subtext}</p>
    </div>
  );
}

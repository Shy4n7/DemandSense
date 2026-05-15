/**
 * SimulationPanel — Inventory depletion simulation with day-by-day playback.
 *
 * Loads historical daily sales data for the selected product, then simulates
 * stock depletion tick by tick. Supports manual restock via the inventory
 * suggestion API.
 *
 * Props: { selectedProduct }
 */

import { useState, useEffect, useRef, useCallback } from 'react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
} from 'recharts';
import { fetchSimulationData, fetchInventory } from '../api/client';
import SkeletonLoader from './SkeletonLoader';
import ErrorMessage from './ErrorMessage';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const SPEED_OPTIONS = [
  { label: 'Slow', value: 800 },
  { label: 'Normal', value: 400 },
  { label: 'Fast', value: 200 },
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmt(n, decimals = 0) {
  return Number(n).toLocaleString(undefined, { maximumFractionDigits: decimals });
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * @param {object}      props
 * @param {string|null} props.selectedProduct
 */
export default function SimulationPanel({ selectedProduct }) {
  // ── Setup inputs ──────────────────────────────────────────────────────────
  const [initialStock, setInitialStock] = useState('');
  const [leadTime, setLeadTime] = useState('7');

  // ── Historical data ───────────────────────────────────────────────────────
  const [historicalData, setHistoricalData] = useState([]);
  const [loadingData, setLoadingData] = useState(false);
  const [errorData, setErrorData] = useState(null);

  // ── Simulation state ──────────────────────────────────────────────────────
  const [simStock, setSimStock] = useState(0);
  const [simDay, setSimDay] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [speed, setSpeed] = useState(400);
  const [simStatus, setSimStatus] = useState('idle'); // idle|running|paused|stockout|complete
  const [pendingRestock, setPendingRestock] = useState(null); // { arrivalDay, units }
  const [restockLog, setRestockLog] = useState([]);
  const [lastInventoryResult, setLastInventoryResult] = useState(null);
  const [orderLoading, setOrderLoading] = useState(false);

  // ── Chart history (accumulated tick by tick) ──────────────────────────────
  const [chartData, setChartData] = useState([]);

  // ── Refs ──────────────────────────────────────────────────────────────────
  const intervalRef = useRef(null);
  // Keep mutable refs for values used inside the interval callback
  const simStockRef = useRef(0);
  const simDayRef = useRef(0);
  const pendingRestockRef = useRef(null);
  const historicalDataRef = useRef([]);
  const lastInventoryResultRef = useRef(null);
  const restockLogRef = useRef([]);
  const chartDataRef = useRef([]);

  // Sync refs whenever state changes
  useEffect(() => { simStockRef.current = simStock; }, [simStock]);
  useEffect(() => { simDayRef.current = simDay; }, [simDay]);
  useEffect(() => { pendingRestockRef.current = pendingRestock; }, [pendingRestock]);
  useEffect(() => { historicalDataRef.current = historicalData; }, [historicalData]);
  useEffect(() => { lastInventoryResultRef.current = lastInventoryResult; }, [lastInventoryResult]);
  useEffect(() => { restockLogRef.current = restockLog; }, [restockLog]);
  useEffect(() => { chartDataRef.current = chartData; }, [chartData]);

  // ── Load historical data when product changes ─────────────────────────────
  useEffect(() => {
    if (!selectedProduct) return;

    // Reset everything when product changes
    _stopInterval();
    setSimStatus('idle');
    setSimStock(0);
    setSimDay(0);
    setIsPlaying(false);
    setPendingRestock(null);
    setRestockLog([]);
    setLastInventoryResult(null);
    setChartData([]);
    setInitialStock('');

    setLoadingData(true);
    setErrorData(null);
    setHistoricalData([]);

    fetchSimulationData(selectedProduct)
      .then((res) => {
        setHistoricalData(res.data);
        setLoadingData(false);
      })
      .catch((err) => {
        setErrorData(err.message || 'Failed to load simulation data.');
        setLoadingData(false);
      });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedProduct]);

  // ── Interval management ───────────────────────────────────────────────────

  function _stopInterval() {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }

  // Cleanup on unmount
  useEffect(() => {
    return () => _stopInterval();
  }, []);

  // Restart interval when speed changes while playing
  useEffect(() => {
    if (isPlaying && simStatus === 'running') {
      _stopInterval();
      intervalRef.current = setInterval(_tick, speed);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [speed]);

  // ── Tick function (runs inside setInterval) ───────────────────────────────

  function _tick() {
    const data = historicalDataRef.current;
    const day = simDayRef.current;
    const reorderPoint = lastInventoryResultRef.current?.reorder_point ?? null;

    if (day >= data.length) {
      _stopInterval();
      setIsPlaying(false);
      setSimStatus('complete');
      return;
    }

    let stock = simStockRef.current;
    const pending = pendingRestockRef.current;
    const todayRecord = data[day];
    const todaySold = todayRecord.actual_quantity;

    // 1. Apply pending restock if it arrives today (restock arrives BEFORE sales)
    if (pending && pending.arrivalDay === day) {
      const stockBefore = stock;
      stock += pending.units;
      const newLog = [
        ...restockLogRef.current,
        {
          day,
          date: todayRecord.date,
          units: pending.units,
          stockBefore,
          stockAfter: stock,
        },
      ];
      setRestockLog(newLog);
      restockLogRef.current = newLog;
      setPendingRestock(null);
      pendingRestockRef.current = null;
    }

    // 2. Decrement stock by today's sales (never below 0)
    stock = Math.max(0, stock - todaySold);

    // 3. Append to chart data
    const newChartPoint = {
      date: todayRecord.date,
      stock,
      reorderPoint,
      sold: todaySold,
    };
    const newChartData = [...chartDataRef.current, newChartPoint];
    setChartData(newChartData);
    chartDataRef.current = newChartData;

    // 4. Update state
    setSimStock(stock);
    simStockRef.current = stock;
    setSimDay(day + 1);
    simDayRef.current = day + 1;

    // 5. Check for stockout
    if (stock === 0) {
      _stopInterval();
      setIsPlaying(false);
      setSimStatus('stockout');
      return;
    }

    // 6. Check for completion
    if (day + 1 >= data.length) {
      _stopInterval();
      setIsPlaying(false);
      setSimStatus('complete');
    }
  }

  // ── Controls ──────────────────────────────────────────────────────────────

  function handleStart(e) {
    e.preventDefault();
    const stockVal = parseFloat(initialStock);
    const leadVal = parseInt(leadTime, 10);
    if (isNaN(stockVal) || stockVal < 0) return;
    if (isNaN(leadVal) || leadVal < 1 || leadVal > 90) return;
    if (historicalData.length === 0) return;

    setSimStock(stockVal);
    simStockRef.current = stockVal;
    setSimDay(0);
    simDayRef.current = 0;
    setPendingRestock(null);
    pendingRestockRef.current = null;
    setRestockLog([]);
    restockLogRef.current = [];
    setChartData([]);
    chartDataRef.current = [];
    setLastInventoryResult(null);
    lastInventoryResultRef.current = null;
    setSimStatus('running');
    setIsPlaying(true);

    _stopInterval();
    intervalRef.current = setInterval(_tick, speed);
  }

  function handlePlayPause() {
    if (isPlaying) {
      _stopInterval();
      setIsPlaying(false);
      setSimStatus('paused');
    } else {
      setIsPlaying(true);
      setSimStatus('running');
      _stopInterval();
      intervalRef.current = setInterval(_tick, speed);
    }
  }

  function handleReset() {
    _stopInterval();
    setSimStatus('idle');
    setSimStock(0);
    setSimDay(0);
    setIsPlaying(false);
    setPendingRestock(null);
    setRestockLog([]);
    setLastInventoryResult(null);
    setChartData([]);
    setInitialStock('');
  }

  // ── Place Order ───────────────────────────────────────────────────────────

  async function handlePlaceOrder() {
    if (!selectedProduct || pendingRestock) return;
    const leadVal = parseInt(leadTime, 10);
    if (isNaN(leadVal) || leadVal < 1) return;

    setOrderLoading(true);
    try {
      const result = await fetchInventory(selectedProduct, simStock, leadVal);
      setLastInventoryResult(result);
      lastInventoryResultRef.current = result;
      const arrivalDay = simDayRef.current + leadVal;
      const newPending = { arrivalDay, units: result.suggested_order };
      setPendingRestock(newPending);
      pendingRestockRef.current = newPending;
    } catch {
      // silently ignore — user can retry
    } finally {
      setOrderLoading(false);
    }
  }

  // ── Derived values ────────────────────────────────────────────────────────

  const reorderPoint = lastInventoryResult?.reorder_point ?? null;
  const daysUntilArrival =
    pendingRestock ? Math.max(0, pendingRestock.arrivalDay - simDay) : null;

  const stockColor =
    simStock === 0
      ? 'text-red-600'
      : reorderPoint !== null && simStock <= reorderPoint
      ? 'text-amber-600'
      : 'text-green-600';

  const canPlaceOrder =
    (simStatus === 'running' || simStatus === 'paused' || simStatus === 'stockout') &&
    !pendingRestock &&
    !orderLoading;

  const currentRecord =
    simDay > 0 && simDay <= historicalData.length
      ? historicalData[simDay - 1]
      : null;

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="rounded-xl border border-gray-200 bg-white shadow-sm">
      {/* Header */}
      <div className="border-b border-gray-100 px-5 py-4">
        <h2 className="text-base font-semibold text-gray-800">Inventory Simulation</h2>
        <p className="mt-0.5 text-xs text-gray-500">
          Day-by-day stock depletion based on historical sales data
        </p>
      </div>

      <div className="px-5 py-4 space-y-5">
        {/* Loading historical data */}
        {loadingData && <SkeletonLoader rows={4} />}

        {/* Error loading data */}
        {!loadingData && errorData && (
          <ErrorMessage message={`Failed to load simulation data. ${errorData}`} />
        )}

        {/* No product selected */}
        {!selectedProduct && !loadingData && (
          <p className="text-sm text-gray-400">Select a product to run a simulation.</p>
        )}

        {/* ── Setup panel (idle) ─────────────────────────────────────────── */}
        {!loadingData && !errorData && selectedProduct && simStatus === 'idle' && (
          <form onSubmit={handleStart} className="space-y-4">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label
                  htmlFor="sim-initial-stock"
                  className="mb-1 block text-xs font-medium text-gray-700"
                >
                  Initial Stock (units)
                </label>
                <input
                  id="sim-initial-stock"
                  type="number"
                  min="0"
                  step="1"
                  placeholder="e.g. 1000"
                  value={initialStock}
                  onChange={(e) => setInitialStock(e.target.value)}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  required
                />
              </div>
              <div>
                <label
                  htmlFor="sim-lead-time"
                  className="mb-1 block text-xs font-medium text-gray-700"
                >
                  Lead Time (days)
                </label>
                <input
                  id="sim-lead-time"
                  type="number"
                  min="1"
                  max="90"
                  step="1"
                  value={leadTime}
                  onChange={(e) => setLeadTime(e.target.value)}
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-900 placeholder-gray-400 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  required
                />
              </div>
            </div>
            <button
              type="submit"
              disabled={!initialStock || !leadTime || historicalData.length === 0}
              className="rounded-lg bg-blue-600 px-5 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Start Simulation
            </button>
            {historicalData.length > 0 && (
              <p className="text-xs text-gray-400">
                {historicalData.length} days of historical data available
              </p>
            )}
          </form>
        )}

        {/* ── Active simulation ──────────────────────────────────────────── */}
        {simStatus !== 'idle' && (
          <div className="space-y-4">
            {/* Playback controls */}
            <div className="flex flex-wrap items-center gap-3">
              {/* Play / Pause */}
              <button
                onClick={handlePlayPause}
                disabled={simStatus === 'complete' || simStatus === 'stockout'}
                className="flex items-center gap-1.5 rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
                aria-label={isPlaying ? 'Pause simulation' : 'Play simulation'}
              >
                {isPlaying ? (
                  <>
                    <span aria-hidden="true">⏸</span> Pause
                  </>
                ) : (
                  <>
                    <span aria-hidden="true">▶</span> Play
                  </>
                )}
              </button>

              {/* Speed selector */}
              <div className="flex rounded-lg border border-gray-200 overflow-hidden">
                {SPEED_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    onClick={() => setSpeed(opt.value)}
                    className={`px-3 py-1.5 text-xs font-medium transition-colors focus:outline-none ${
                      speed === opt.value
                        ? 'bg-blue-600 text-white'
                        : 'bg-white text-gray-600 hover:bg-gray-50'
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>

              {/* Reset */}
              <button
                onClick={handleReset}
                className="rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500"
                aria-label="Reset simulation"
              >
                Reset
              </button>
            </div>

            {/* Status banners */}
            {simStatus === 'stockout' && currentRecord && (
              <div
                className="flex items-start gap-2 rounded-lg border border-red-300 bg-red-50 px-4 py-3"
                role="alert"
              >
                <span className="text-lg leading-none">⚠</span>
                <p className="text-sm font-semibold text-red-700">
                  Stockout on {currentRecord.date} — place an order to restock
                </p>
              </div>
            )}
            {simStatus === 'complete' && (
              <div
                className="flex items-start gap-2 rounded-lg border border-green-300 bg-green-50 px-4 py-3"
                role="status"
              >
                <span className="text-lg leading-none">✓</span>
                <p className="text-sm font-semibold text-green-700">
                  Simulation complete — {simDay} days survived
                </p>
              </div>
            )}

            {/* Stock gauge */}
            <div className="rounded-xl border border-gray-100 bg-gray-50 p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                Current Stock
              </p>
              <p className={`mt-1 text-5xl font-bold tabular-nums ${stockColor}`}>
                {fmt(simStock)}
              </p>
              {reorderPoint !== null && (
                <p className="mt-1 text-xs text-gray-400">
                  Reorder point: {fmt(reorderPoint, 1)} units
                </p>
              )}
            </div>

            {/* Daily info bar */}
            {currentRecord && (
              <div className="grid grid-cols-3 gap-3">
                <InfoTile label="Current Date" value={currentRecord.date} />
                <InfoTile
                  label="Units Sold Today"
                  value={fmt(currentRecord.actual_quantity)}
                />
                <InfoTile label="Day" value={`${simDay} / ${historicalData.length}`} />
              </div>
            )}

            {/* Place Order */}
            <div className="flex flex-wrap items-center gap-3">
              <button
                onClick={handlePlaceOrder}
                disabled={!canPlaceOrder}
                className="rounded-lg bg-amber-500 px-5 py-2 text-sm font-medium text-white transition-colors hover:bg-amber-600 focus:outline-none focus:ring-2 focus:ring-amber-400 focus:ring-offset-1 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {orderLoading ? 'Calculating…' : 'Place Order'}
              </button>
              {pendingRestock && (
                <p className="text-xs text-gray-500">
                  Order in transit — arrives in{' '}
                  <span className="font-semibold text-blue-600">
                    {daysUntilArrival} day{daysUntilArrival !== 1 ? 's' : ''}
                  </span>{' '}
                  ({fmt(pendingRestock.units)} units)
                </p>
              )}
            </div>

            {/* Inventory chart */}
            {chartData.length > 0 && (
              <div className="rounded-xl border border-gray-100 bg-white p-3">
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">
                  Stock Level Over Time
                </p>
                <ResponsiveContainer width="100%" height={200}>
                  <AreaChart
                    data={chartData}
                    margin={{ top: 5, right: 10, left: 0, bottom: 5 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                    <XAxis
                      dataKey="date"
                      tick={{ fontSize: 10 }}
                      tickFormatter={(v) => v.slice(5)}
                      interval="preserveStartEnd"
                    />
                    <YAxis tick={{ fontSize: 10 }} width={50} />
                    <Tooltip
                      formatter={(value, name) => [fmt(value, 0), name]}
                      labelFormatter={(label) => `Date: ${label}`}
                    />
                    {reorderPoint !== null && (
                      <ReferenceLine
                        y={reorderPoint}
                        stroke="#f59e0b"
                        strokeDasharray="4 3"
                        label={{
                          value: 'Reorder',
                          position: 'insideTopRight',
                          fontSize: 10,
                          fill: '#f59e0b',
                        }}
                      />
                    )}
                    <Area
                      type="monotone"
                      dataKey="stock"
                      stroke="#3b82f6"
                      fill="#bfdbfe"
                      fillOpacity={0.5}
                      name="Stock"
                      dot={false}
                      isAnimationActive={false}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* Restock log */}
            {restockLog.length > 0 && (
              <div>
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">
                  Restock Log
                </p>
                <div className="overflow-auto rounded-lg border border-gray-100" style={{ maxHeight: '160px' }}>
                  <table className="w-full text-xs">
                    <thead className="sticky top-0 bg-gray-50">
                      <tr className="border-b border-gray-100 text-left text-gray-500">
                        <th className="px-3 py-2">Day</th>
                        <th className="px-3 py-2">Date</th>
                        <th className="px-3 py-2">Units Ordered</th>
                        <th className="px-3 py-2">Stock Before</th>
                        <th className="px-3 py-2">Stock After</th>
                      </tr>
                    </thead>
                    <tbody>
                      {restockLog.map((entry, i) => (
                        <tr
                          key={i}
                          className="border-b border-gray-50 last:border-0 hover:bg-gray-50"
                        >
                          <td className="px-3 py-1.5 font-mono">{entry.day}</td>
                          <td className="px-3 py-1.5 font-mono">{entry.date}</td>
                          <td className="px-3 py-1.5 font-semibold text-green-700">
                            +{fmt(entry.units)}
                          </td>
                          <td className="px-3 py-1.5">{fmt(entry.stockBefore)}</td>
                          <td className="px-3 py-1.5 font-semibold">{fmt(entry.stockAfter)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function InfoTile({ label, value }) {
  return (
    <div className="rounded-lg border border-gray-100 bg-gray-50 p-3">
      <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">{label}</p>
      <p className="mt-0.5 text-sm font-bold text-gray-900 tabular-nums">{value}</p>
    </div>
  );
}

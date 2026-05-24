/**
 * App — root component for DemandSense.
 *
 * Holds all application state and orchestrates data fetching across all four
 * API endpoints. Each data region (forecast, anomalies, inventory, products)
 * has independent loading and error state so a failure in one region never
 * blanks out the others.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import {
  fetchProducts,
  fetchForecast,
  fetchAnomalies,
  fetchInventory,
} from './api/client';
import ProductSelector   from './components/ProductSelector';
import MetricsCards      from './components/MetricsCards';
import ForecastChart     from './components/ForecastChart';
import AnomalyTable      from './components/AnomalyTable';
import GlobalOverview    from './components/GlobalOverview';
import InventoryPlanner  from './components/InventoryPlanner';

// ---------------------------------------------------------------------------
// Initial state
// ---------------------------------------------------------------------------

const INITIAL_STATE = {
  products:        [],
  selectedProduct: null,
  horizon:         14,
  forecast:        null,
  anomalies:       null,
  inventory:       null,
  loading: {
    products:  false,
    forecast:  false,
    anomalies: false,
    inventory: false,
  },
  errors: {
    products:  null,
    forecast:  null,
    anomalies: null,
    inventory: null,
  },
};

// ---------------------------------------------------------------------------
// App component
// ---------------------------------------------------------------------------

export default function App() {
  const [state, setState]           = useState(INITIAL_STATE);
  const [yAxisUnit, setYAxisUnit]   = useState('quantity');

  // Inventory planner controls — persisted at App level so changing
  // stock/lead-time re-fetches without losing the currently selected product.
  const [currentStock,  setCurrentStock]  = useState(50);
  const [leadTime,      setLeadTime]      = useState(7);
  const [serviceLevel,  setServiceLevel]  = useState(0.95);

  // Generation counter prevents stale responses from overwriting newer state.
  const fetchGenRef = useRef(0);

  // ---------------------------------------------------------------------------
  // Helper: update nested loading / error slices
  // ---------------------------------------------------------------------------

  function setLoading(keys, value) {
    setState((prev) => ({
      ...prev,
      loading: keys.reduce((acc, k) => ({ ...acc, [k]: value }), { ...prev.loading }),
    }));
  }

  // ---------------------------------------------------------------------------
  // Load products on mount
  // ---------------------------------------------------------------------------

  useEffect(() => {
    async function loadProducts() {
      setState((prev) => ({
        ...prev,
        loading: { ...prev.loading, products: true },
        errors:  { ...prev.errors,  products: null },
      }));

      try {
        const products = await fetchProducts();
        setState((prev) => ({
          ...prev,
          products,
          loading: { ...prev.loading, products: false },
        }));
      } catch (err) {
        setState((prev) => ({
          ...prev,
          loading: { ...prev.loading, products: false },
          errors:  { ...prev.errors,  products: err.message || 'Failed to load products.' },
        }));
      }
    }
    loadProducts();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ---------------------------------------------------------------------------
  // Select product — fire 3 parallel fetches
  // ---------------------------------------------------------------------------

  function selectProduct(productId) {
    const gen = ++fetchGenRef.current;

    setState((prev) => ({
      ...prev,
      selectedProduct: productId,
      forecast:        null,
      anomalies:       null,
      inventory:       null,
      loading: { ...prev.loading, forecast: true, anomalies: true, inventory: true },
      errors:  { ...prev.errors,  forecast: null, anomalies: null, inventory: null },
    }));

    const currentHorizon = state.horizon;

    // Forecast
    fetchForecast(productId, currentHorizon)
      .then((data) => {
        if (fetchGenRef.current !== gen) return;
        setState((prev) => ({
          ...prev,
          forecast: data,
          loading:  { ...prev.loading, forecast: false },
          errors:   { ...prev.errors,  forecast: null },
        }));
      })
      .catch((err) => {
        if (fetchGenRef.current !== gen) return;
        setState((prev) => ({
          ...prev,
          loading: { ...prev.loading, forecast: false },
          errors:  { ...prev.errors,  forecast: err.message || 'Failed to load forecast data.' },
        }));
      });

    // Anomalies
    fetchAnomalies(productId)
      .then((data) => {
        if (fetchGenRef.current !== gen) return;
        setState((prev) => ({
          ...prev,
          anomalies: data,
          loading:   { ...prev.loading, anomalies: false },
          errors:    { ...prev.errors,  anomalies: null },
        }));
      })
      .catch((err) => {
        if (fetchGenRef.current !== gen) return;
        setState((prev) => ({
          ...prev,
          loading: { ...prev.loading, anomalies: false },
          errors:  { ...prev.errors,  anomalies: err.message || 'Failed to load anomaly data.' },
        }));
      });

    // Inventory
    fetchInventory(productId, currentStock, leadTime, serviceLevel)
      .then((data) => {
        if (fetchGenRef.current !== gen) return;
        setState((prev) => ({
          ...prev,
          inventory: data,
          loading:   { ...prev.loading, inventory: false },
          errors:    { ...prev.errors,  inventory: null },
        }));
      })
      .catch((err) => {
        if (fetchGenRef.current !== gen) return;
        setState((prev) => ({
          ...prev,
          loading: { ...prev.loading, inventory: false },
          errors:  { ...prev.errors,  inventory: err.message || 'Failed to load stock data.' },
        }));
      });
  }

  // ---------------------------------------------------------------------------
  // Re-fetch inventory whenever planner inputs change (and a product is selected)
  // ---------------------------------------------------------------------------

  function refetchInventory(productId, stock, lead, sl) {
    if (!productId) return;
    const gen = ++fetchGenRef.current;

    setState((prev) => ({
      ...prev,
      inventory: null,
      loading:   { ...prev.loading, inventory: true },
      errors:    { ...prev.errors,  inventory: null },
    }));

    fetchInventory(productId, stock, lead, sl)
      .then((data) => {
        if (fetchGenRef.current !== gen) return;
        setState((prev) => ({
          ...prev,
          inventory: data,
          loading:   { ...prev.loading, inventory: false },
          errors:    { ...prev.errors,  inventory: null },
        }));
      })
      .catch((err) => {
        if (fetchGenRef.current !== gen) return;
        setState((prev) => ({
          ...prev,
          loading: { ...prev.loading, inventory: false },
          errors:  { ...prev.errors,  inventory: err.message || 'Failed to load stock data.' },
        }));
      });
  }

  // Planner setters that also trigger re-fetch
  function handleCurrentStockChange(val) {
    setCurrentStock(val);
    refetchInventory(state.selectedProduct, val, leadTime, serviceLevel);
  }
  function handleLeadTimeChange(val) {
    setLeadTime(val);
    refetchInventory(state.selectedProduct, currentStock, val, serviceLevel);
  }
  function handleServiceLevelChange(val) {
    setServiceLevel(val);
    refetchInventory(state.selectedProduct, currentStock, leadTime, val);
  }

  // ---------------------------------------------------------------------------
  // Handle product change from ProductSelector
  // ---------------------------------------------------------------------------

  function handleProductSelect(productId) {
    if (productId === state.selectedProduct) return;
    selectProduct(productId);
  }

  // ---------------------------------------------------------------------------
  // Handle horizon change — re-fetch forecast only
  // ---------------------------------------------------------------------------

  function handleHorizonChange(newHorizon) {
    if (newHorizon === state.horizon || !state.selectedProduct) return;

    const gen       = ++fetchGenRef.current;
    const productId = state.selectedProduct;

    setState((prev) => ({
      ...prev,
      horizon:  newHorizon,
      forecast: null,
      loading:  { ...prev.loading, forecast: true },
      errors:   { ...prev.errors,  forecast: null },
    }));

    fetchForecast(productId, newHorizon)
      .then((data) => {
        if (fetchGenRef.current !== gen) return;
        setState((prev) => ({
          ...prev,
          forecast: data,
          loading:  { ...prev.loading, forecast: false },
          errors:   { ...prev.errors,  forecast: null },
        }));
      })
      .catch((err) => {
        if (fetchGenRef.current !== gen) return;
        setState((prev) => ({
          ...prev,
          loading: { ...prev.loading, forecast: false },
          errors:  { ...prev.errors,  forecast: err.message || 'Failed to load forecast data.' },
        }));
      });
  }

  // ---------------------------------------------------------------------------
  // Retry handlers
  // ---------------------------------------------------------------------------

  const retryForecast = useCallback(() => {
    if (!state.selectedProduct) return;
    const gen       = ++fetchGenRef.current;
    const productId = state.selectedProduct;
    const horizon   = state.horizon;

    setState((prev) => ({
      ...prev,
      forecast: null,
      loading:  { ...prev.loading, forecast: true },
      errors:   { ...prev.errors,  forecast: null },
    }));

    fetchForecast(productId, horizon)
      .then((data) => {
        if (fetchGenRef.current !== gen) return;
        setState((prev) => ({ ...prev, forecast: data, loading: { ...prev.loading, forecast: false }, errors: { ...prev.errors, forecast: null } }));
      })
      .catch((err) => {
        if (fetchGenRef.current !== gen) return;
        setState((prev) => ({ ...prev, loading: { ...prev.loading, forecast: false }, errors: { ...prev.errors, forecast: err.message || 'Failed to load forecast data.' } }));
      });
  }, [state.selectedProduct, state.horizon]);

  const retryAnomalies = useCallback(() => {
    if (!state.selectedProduct) return;
    const gen       = ++fetchGenRef.current;
    const productId = state.selectedProduct;

    setState((prev) => ({
      ...prev,
      anomalies: null,
      loading:   { ...prev.loading, anomalies: true },
      errors:    { ...prev.errors,  anomalies: null },
    }));

    fetchAnomalies(productId)
      .then((data) => {
        if (fetchGenRef.current !== gen) return;
        setState((prev) => ({ ...prev, anomalies: data, loading: { ...prev.loading, anomalies: false }, errors: { ...prev.errors, anomalies: null } }));
      })
      .catch((err) => {
        if (fetchGenRef.current !== gen) return;
        setState((prev) => ({ ...prev, loading: { ...prev.loading, anomalies: false }, errors: { ...prev.errors, anomalies: err.message || 'Failed to load anomaly data.' } }));
      });
  }, [state.selectedProduct]);

  // ---------------------------------------------------------------------------
  // Destructure for readability
  // ---------------------------------------------------------------------------

  const {
    products, selectedProduct, horizon,
    forecast, anomalies, inventory,
    loading, errors,
  } = state;

  const selectedProductObj = products.find((p) => p.product_id === selectedProduct);
  const unitPrice          = selectedProductObj?.unit_price ?? 0.0;
  const history            = (forecast?.history ?? []).slice(-90);

  const hasProductSelected = selectedProduct !== null;

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-indigo-950 to-slate-900 text-slate-100 pb-12">

      <header className="border-b border-white/10 bg-slate-950/40 backdrop-blur-md px-6 py-4 shadow-lg sticky top-0 z-50">
        <div className="mx-auto flex flex-col sm:flex-row max-w-7xl sm:items-center justify-between gap-2">
          <div>
            <h1 className="text-xl font-bold text-white">DemandSense</h1>
            <p className="text-xs text-slate-500 mt-0.5">Store Management Dashboard</p>
          </div>
          {hasProductSelected && selectedProductObj && (
            <p className="text-sm text-slate-300">
              Viewing:{' '}
              <span className="font-semibold text-white">{selectedProductObj.description}</span>
            </p>
          )}
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-6 py-6 space-y-6">

        {/* Product selector row */}
        <div className="flex flex-col sm:flex-row sm:items-end gap-4">
          <div className="w-full sm:max-w-sm">
            <ProductSelector
              products={products}
              selectedProduct={selectedProduct}
              onSelect={handleProductSelect}
              loading={loading.products}
              error={errors.products}
            />
          </div>
          <div>
            <button
              onClick={() => setState((prev) => ({ ...prev, selectedProduct: null }))}
              className={`w-full sm:w-auto px-4 py-2.5 rounded-lg text-sm font-medium transition-all duration-300 ${
                selectedProduct === null
                  ? 'bg-indigo-600/30 text-indigo-300 border border-indigo-500/40 shadow-[0_0_15px_rgba(99,102,241,0.25)]'
                  : 'bg-white/5 text-slate-300 border border-white/10 hover:bg-white/10 hover:text-white'
              }`}
            >
              Dashboard Overview
            </button>
          </div>
        </div>

        {/* ---- GLOBAL OVERVIEW ---- */}
        {!hasProductSelected && !loading.products && !errors.products && (
          <GlobalOverview
            products={products}
            onSelectProduct={handleProductSelect}
          />
        )}

        {/* ---- PRODUCT DETAIL VIEW ---- */}
        {hasProductSelected && (
          <>
            {/* 3-card summary */}
            <MetricsCards
              forecast={forecast}
              anomalies={anomalies}
              inventory={inventory}
              loadingForecast={loading.forecast}
              loadingAnomalies={loading.anomalies}
              loadingInventory={loading.inventory}
              errorForecast={errors.forecast}
              errorAnomalies={errors.anomalies}
              errorInventory={errors.inventory}
              unitPrice={unitPrice}
              yAxisUnit={yAxisUnit}
            />

            {/* Sales trend chart */}
            <ForecastChart
              forecast={forecast}
              history={history}
              loading={loading.forecast}
              error={errors.forecast}
              horizon={horizon}
              onHorizonChange={handleHorizonChange}
              onRetry={retryForecast}
              unitPrice={unitPrice}
              yAxisUnit={yAxisUnit}
              onUnitChange={setYAxisUnit}
            />

            {/* Alerts list */}
            <AnomalyTable
              anomalies={anomalies}
              loading={loading.anomalies}
              error={errors.anomalies}
              onRetry={retryAnomalies}
            />
          </>
        )}
      </main>
    </div>
  );
}

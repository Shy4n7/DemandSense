/**
 * App — root component for DemandSense.
 *
 * Holds all application state and orchestrates data fetching across all four
 * API endpoints. Each data region (forecast, anomalies, importance, products)
 * has independent loading and error state so a failure in one region never
 * blanks out the others.
 *
 * Requirements: 8.2, 8.3, 8.4, 8.5, 9.3, 9.4, 10.4, 14.1, 14.2, 14.3, 14.4, 14.5
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import {
  fetchProducts,
  fetchForecast,
  fetchAnomalies,
  fetchImportance,
} from './api/client';
import ProductSelector from './components/ProductSelector';
import MetricsCards from './components/MetricsCards';
import ForecastChart from './components/ForecastChart';
import AnomalyTable from './components/AnomalyTable';
import FeatureImportance from './components/FeatureImportance';
import InventoryPanel from './components/InventoryPanel';
import SimulationPanel from './components/SimulationPanel';

// ---------------------------------------------------------------------------
// Initial state
// ---------------------------------------------------------------------------

const INITIAL_STATE = {
  products: [],
  selectedProduct: null,
  horizon: 14,
  forecast: null,
  anomalies: null,
  importance: null,
  inventory: null,
  loading: {
    products: false,
    forecast: false,
    anomalies: false,
    importance: false,
    inventory: false,
  },
  errors: {
    products: null,
    forecast: null,
    anomalies: null,
    importance: null,
    inventory: null,
  },
};

// ---------------------------------------------------------------------------
// App component
// ---------------------------------------------------------------------------

export default function App() {
  const [state, setState] = useState(INITIAL_STATE);

  // Track the "current" product fetch generation so stale responses from a
  // previous product selection are silently discarded.
  const fetchGenRef = useRef(0);

  // ---------------------------------------------------------------------------
  // Helpers to update nested loading / error slices
  // ---------------------------------------------------------------------------

  function setLoading(keys, value) {
    setState((prev) => ({
      ...prev,
      loading: keys.reduce(
        (acc, k) => ({ ...acc, [k]: value }),
        { ...prev.loading }
      ),
    }));
  }

  function setError(key, message) {
    setState((prev) => ({
      ...prev,
      errors: { ...prev.errors, [key]: message },
    }));
  }

  // ---------------------------------------------------------------------------
  // Fetch products on mount (Requirement 8.5)
  // ---------------------------------------------------------------------------

  useEffect(() => {
    async function loadProducts() {
      setState((prev) => ({
        ...prev,
        loading: { ...prev.loading, products: true },
        errors: { ...prev.errors, products: null },
      }));

      try {
        const products = await fetchProducts();

        setState((prev) => ({
          ...prev,
          products,
          loading: { ...prev.loading, products: false },
        }));

        // Auto-select the first product (Requirement 8.5)
        if (products.length > 0) {
          selectProduct(products[0].product_id, products);
        }
      } catch (err) {
        // Requirement 14.5: show error in product selector region
        setState((prev) => ({
          ...prev,
          loading: { ...prev.loading, products: false },
          errors: {
            ...prev.errors,
            products: err.message || 'Failed to load products.',
          },
        }));
      }
    }

    loadProducts();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ---------------------------------------------------------------------------
  // Select a product — fires 3 parallel fetches (Requirement 8.2)
  // ---------------------------------------------------------------------------

  function selectProduct(productId, productList) {
    // Bump generation so any in-flight fetches for the old product are ignored
    const gen = ++fetchGenRef.current;

    setState((prev) => ({
      ...prev,
      selectedProduct: productId,
      // Reset all data and loading states (Requirement 10.4)
      forecast: null,
      anomalies: null,
      importance: null,
      loading: {
        ...prev.loading,
        forecast: true,
        anomalies: true,
        importance: true,
      },
      errors: {
        ...prev.errors,
        forecast: null,
        anomalies: null,
        importance: null,
      },
    }));

    const currentHorizon = state.horizon;

    // Forecast
    fetchForecast(productId, currentHorizon)
      .then((data) => {
        if (fetchGenRef.current !== gen) return;
        setState((prev) => ({
          ...prev,
          forecast: data,
          loading: { ...prev.loading, forecast: false },
          errors: { ...prev.errors, forecast: null },
        }));
      })
      .catch((err) => {
        if (fetchGenRef.current !== gen) return;
        setState((prev) => ({
          ...prev,
          loading: { ...prev.loading, forecast: false },
          errors: {
            ...prev.errors,
            forecast: err.message || 'Failed to load forecast data.',
          },
        }));
      });

    // Anomalies
    fetchAnomalies(productId)
      .then((data) => {
        if (fetchGenRef.current !== gen) return;
        setState((prev) => ({
          ...prev,
          anomalies: data,
          loading: { ...prev.loading, anomalies: false },
          errors: { ...prev.errors, anomalies: null },
        }));
      })
      .catch((err) => {
        if (fetchGenRef.current !== gen) return;
        setState((prev) => ({
          ...prev,
          loading: { ...prev.loading, anomalies: false },
          errors: {
            ...prev.errors,
            anomalies: err.message || 'Failed to load anomaly data.',
          },
        }));
      });

    // Importance
    fetchImportance(productId)
      .then((data) => {
        if (fetchGenRef.current !== gen) return;
        setState((prev) => ({
          ...prev,
          importance: data,
          loading: { ...prev.loading, importance: false },
          errors: { ...prev.errors, importance: null },
        }));
      })
      .catch((err) => {
        if (fetchGenRef.current !== gen) return;
        setState((prev) => ({
          ...prev,
          loading: { ...prev.loading, importance: false },
          errors: {
            ...prev.errors,
            importance: err.message || 'Failed to load feature importance data.',
          },
        }));
      });
  }

  // ---------------------------------------------------------------------------
  // Handle product change from ProductSelector
  // ---------------------------------------------------------------------------

  function handleProductSelect(productId) {
    if (productId === state.selectedProduct) return;
    selectProduct(productId, state.products);
  }

  // ---------------------------------------------------------------------------
  // Handle horizon change — re-fetch forecast only (Requirement 9.4)
  // ---------------------------------------------------------------------------

  function handleHorizonChange(newHorizon) {
    if (newHorizon === state.horizon || !state.selectedProduct) return;

    const gen = ++fetchGenRef.current;
    const productId = state.selectedProduct;

    setState((prev) => ({
      ...prev,
      horizon: newHorizon,
      forecast: null,
      loading: { ...prev.loading, forecast: true },
      errors: { ...prev.errors, forecast: null },
    }));

    fetchForecast(productId, newHorizon)
      .then((data) => {
        if (fetchGenRef.current !== gen) return;
        setState((prev) => ({
          ...prev,
          forecast: data,
          loading: { ...prev.loading, forecast: false },
          errors: { ...prev.errors, forecast: null },
        }));
      })
      .catch((err) => {
        if (fetchGenRef.current !== gen) return;
        setState((prev) => ({
          ...prev,
          loading: { ...prev.loading, forecast: false },
          errors: {
            ...prev.errors,
            forecast: err.message || 'Failed to load forecast data.',
          },
        }));
      });
  }

  // ---------------------------------------------------------------------------
  // Retry handlers — re-fetch a single region (Requirement 14.1)
  // ---------------------------------------------------------------------------

  const retryForecast = useCallback(() => {
    if (!state.selectedProduct) return;
    const gen = ++fetchGenRef.current;
    const productId = state.selectedProduct;
    const horizon = state.horizon;

    setState((prev) => ({
      ...prev,
      forecast: null,
      loading: { ...prev.loading, forecast: true },
      errors: { ...prev.errors, forecast: null },
    }));

    fetchForecast(productId, horizon)
      .then((data) => {
        if (fetchGenRef.current !== gen) return;
        setState((prev) => ({
          ...prev,
          forecast: data,
          loading: { ...prev.loading, forecast: false },
          errors: { ...prev.errors, forecast: null },
        }));
      })
      .catch((err) => {
        if (fetchGenRef.current !== gen) return;
        setState((prev) => ({
          ...prev,
          loading: { ...prev.loading, forecast: false },
          errors: {
            ...prev.errors,
            forecast: err.message || 'Failed to load forecast data.',
          },
        }));
      });
  }, [state.selectedProduct, state.horizon]);

  const retryAnomalies = useCallback(() => {
    if (!state.selectedProduct) return;
    const gen = ++fetchGenRef.current;
    const productId = state.selectedProduct;

    setState((prev) => ({
      ...prev,
      anomalies: null,
      loading: { ...prev.loading, anomalies: true },
      errors: { ...prev.errors, anomalies: null },
    }));

    fetchAnomalies(productId)
      .then((data) => {
        if (fetchGenRef.current !== gen) return;
        setState((prev) => ({
          ...prev,
          anomalies: data,
          loading: { ...prev.loading, anomalies: false },
          errors: { ...prev.errors, anomalies: null },
        }));
      })
      .catch((err) => {
        if (fetchGenRef.current !== gen) return;
        setState((prev) => ({
          ...prev,
          loading: { ...prev.loading, anomalies: false },
          errors: {
            ...prev.errors,
            anomalies: err.message || 'Failed to load anomaly data.',
          },
        }));
      });
  }, [state.selectedProduct]);

  const retryImportance = useCallback(() => {
    if (!state.selectedProduct) return;
    const gen = ++fetchGenRef.current;
    const productId = state.selectedProduct;

    setState((prev) => ({
      ...prev,
      importance: null,
      loading: { ...prev.loading, importance: true },
      errors: { ...prev.errors, importance: null },
    }));

    fetchImportance(productId)
      .then((data) => {
        if (fetchGenRef.current !== gen) return;
        setState((prev) => ({
          ...prev,
          importance: data,
          loading: { ...prev.loading, importance: false },
          errors: { ...prev.errors, importance: null },
        }));
      })
      .catch((err) => {
        if (fetchGenRef.current !== gen) return;
        setState((prev) => ({
          ...prev,
          loading: { ...prev.loading, importance: false },
          errors: {
            ...prev.errors,
            importance: err.message || 'Failed to load feature importance data.',
          },
        }));
      });
  }, [state.selectedProduct]);

  // ---------------------------------------------------------------------------
  // Destructure state for readability
  // ---------------------------------------------------------------------------

  const {
    products,
    selectedProduct,
    horizon,
    forecast,
    anomalies,
    importance,
    loading,
    errors,
  } = state;

  // Historical actuals extracted from forecast response for ForecastChart
  const history = forecast?.history ?? [];

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Top bar */}
      <header className="border-b border-gray-200 bg-white px-6 py-4 shadow-sm">
        <div className="mx-auto flex max-w-7xl items-center justify-between">
          <h1 className="text-xl font-bold text-gray-900">DemandSense</h1>
          <p className="text-sm text-gray-500">Retail Demand Forecasting &amp; Anomaly Detection</p>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-6 py-6 space-y-6">
        {/* Product selector row */}
        <div className="flex items-start gap-4">
          <ProductSelector
            products={products}
            selectedProduct={selectedProduct}
            onSelect={handleProductSelect}
            loading={loading.products}
            error={errors.products}
          />
        </div>

        {/* "Select a product" prompt — always visible when no product is selected
            (Requirement 14.4) */}
        {!selectedProduct && !loading.products && !errors.products && (
          <div className="rounded-xl border border-blue-100 bg-blue-50 px-6 py-10 text-center">
            <p className="text-base text-blue-700">
              Select a product to view demand forecasts and anomalies
            </p>
          </div>
        )}

        {/* Metrics cards — shown whenever a product is selected or being loaded */}
        {(selectedProduct || loading.forecast || loading.anomalies) && (
          <MetricsCards
            forecast={forecast}
            anomalies={anomalies}
            loadingForecast={loading.forecast}
            loadingAnomalies={loading.anomalies}
            errorForecast={errors.forecast}
            errorAnomalies={errors.anomalies}
          />
        )}

        {/* Main content grid: chart + sidebar */}
        {(selectedProduct || loading.forecast || loading.importance) && (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            {/* Left / main column: forecast chart + anomaly table */}
            <div className="space-y-6 lg:col-span-2">
              <ForecastChart
                forecast={forecast}
                history={history}
                loading={loading.forecast}
                error={errors.forecast}
                horizon={horizon}
                onHorizonChange={handleHorizonChange}
                onRetry={retryForecast}
              />

              <AnomalyTable
                anomalies={anomalies}
                loading={loading.anomalies}
                error={errors.anomalies}
                onRetry={retryAnomalies}
              />

              <InventoryPanel selectedProduct={selectedProduct} />

              <SimulationPanel selectedProduct={selectedProduct} />
            </div>

            {/* Right / sidebar column: feature importance */}
            <div className="lg:col-span-1">
              <FeatureImportance
                importance={importance}
                loading={loading.importance}
                error={errors.importance}
                onRetry={retryImportance}
              />
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

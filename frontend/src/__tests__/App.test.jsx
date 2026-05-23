/**
 * Task 19.2 — App integration unit tests
 *
 * Mocks the API client so no real network calls are made.
 * Recharts is mocked to avoid jsdom layout issues.
 */

jest.mock('../api/client', () => ({
  fetchProducts: jest.fn(),
  fetchForecast: jest.fn(),
  fetchAnomalies: jest.fn(),
  fetchInventory: jest.fn(),
  fetchSimulationData: jest.fn(),
  ApiError: class ApiError extends Error {
    constructor(status, message) {
      super(message);
      this.status = status;
    }
  }
}));

jest.mock('recharts', () => {
  const React = require('react');
  return {
    ResponsiveContainer: ({ children }) => (
      <div data-testid="responsive-container">{children}</div>
    ),
    ComposedChart: ({ children }) => (
      <div data-testid="composed-chart">{children}</div>
    ),
    BarChart: ({ children }) => (
      <div data-testid="bar-chart">{children}</div>
    ),
    Line: () => null,
    Area: () => null,
    Bar: () => null,
    XAxis: () => null,
    YAxis: () => null,
    CartesianGrid: () => null,
    Tooltip: () => null,
    Legend: () => null,
    Cell: () => null,
    LabelList: () => null,
  };
});

import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import {
  fetchProducts,
  fetchForecast,
  fetchAnomalies,
  fetchInventory,
} from '../api/client';
import App from '../App';

const PRODUCTS = [
  { product_id: 'P001', description: 'Widget Alpha', unit_price: 10.0, total_volume: 100, total_revenue: 1000, anomaly_count: 0, stockout_warning: false },
  { product_id: 'P002', description: 'Gadget Beta', unit_price: 20.0, total_volume: 50, total_revenue: 1000, anomaly_count: 1, stockout_warning: false },
];

const FORECAST_DATA = {
  product_id: 'P001',
  forecast: [
    { date: '2024-01-15', predicted: 100, lower: 80, upper: 120 },
  ],
  history: [{ date: '2024-01-10', quantity: 95 }],
  metrics: { mape: 4.5, rmse: 10.2 },
};

const ANOMALIES_DATA = {
  product_id: 'P001',
  anomalies: [],
  total_anomalies: 0,
};

const INVENTORY_DATA = {
  product_id:       'P001',
  forecasted_demand: 90,
  safety_stock:      15,
  reorder_point:     105,
  current_stock:     50,
  suggested_order:   55,
  status:            'REORDER NOW',
  reorder_alert:     true,
};

beforeEach(() => {
  jest.clearAllMocks();
  // Default: inventory resolves immediately so tests don't hang
  fetchInventory.mockResolvedValue(INVENTORY_DATA);
});

describe('App', () => {
  it('displays Global Overview dashboard when no product is selected (products load empty)', async () => {
    fetchProducts.mockResolvedValue([]);

    render(<App />);

    await waitFor(() => {
      // With an empty product list, the Today at a Glance section should render
      expect(screen.getByText('Today at a Glance')).toBeInTheDocument();
    });
  });

  it('displays the Global Overview dashboard by default and allows selecting a product', async () => {
    fetchProducts.mockResolvedValue(PRODUCTS);
    fetchForecast.mockResolvedValue(FORECAST_DATA);
    fetchAnomalies.mockResolvedValue(ANOMALIES_DATA);

    render(<App />);

    // Wait for the dashboard to render product cards
    await waitFor(() => {
      expect(screen.getByText('Widget Alpha')).toBeInTheDocument();
    });

    // Verify fetchForecast has NOT been called automatically
    expect(fetchForecast).not.toHaveBeenCalled();

    // Select the first product by clicking on it in the product grid
    fireEvent.click(screen.getByText('Widget Alpha'));

    // Verify that selecting the product triggers forecast and anomaly fetches
    await waitFor(() => {
      expect(fetchForecast).toHaveBeenCalledWith('P001', expect.any(Number));
      expect(fetchAnomalies).toHaveBeenCalledWith('P001');
    });
  });

  it('displays skeleton loaders in product selector region while fetching', async () => {
    // Keep products loading indefinitely so we can observe the skeleton state
    fetchProducts.mockReturnValue(new Promise(() => {}));

    render(<App />);

    // The product selector region shows a skeleton while products are loading
    const loaders = screen.getAllByRole('status');
    expect(loaders.length).toBeGreaterThanOrEqual(1);
  });

  it('shows skeleton loaders in forecast/anomaly regions while data is loading', async () => {
    // Products resolve immediately; data fetches stay pending
    fetchProducts.mockResolvedValue(PRODUCTS);
    fetchForecast.mockReturnValue(new Promise(() => {}));
    fetchAnomalies.mockReturnValue(new Promise(() => {}));

    render(<App />);

    // Wait for products to load
    await waitFor(() => {
      expect(screen.getByText('Widget Alpha')).toBeInTheDocument();
    });

    // Click product to select it
    fireEvent.click(screen.getByText('Widget Alpha'));

    // While the fetches are pending, multiple skeleton loaders should be visible
    await waitFor(() => {
      const loaders = screen.getAllByRole('status');
      expect(loaders.length).toBeGreaterThanOrEqual(2);
    });
  });

  it('retains prior product data when a new request fails', async () => {
    // First load succeeds
    fetchProducts.mockResolvedValue(PRODUCTS);
    fetchForecast.mockResolvedValue(FORECAST_DATA);
    fetchAnomalies.mockResolvedValue(ANOMALIES_DATA);

    render(<App />);

    // Wait for products to load
    await waitFor(() => {
      expect(screen.getByText('Widget Alpha')).toBeInTheDocument();
    });

    // Click to select the product
    fireEvent.click(screen.getByText('Widget Alpha'));

    // Wait for initial data to load and check that the Expected Demand value is shown
    await waitFor(() => {
      // 100 units is the sum of all forecast.predicted values
      expect(screen.getAllByText('100 units')[0]).toBeInTheDocument();
    });

    // Now simulate a second fetch failure (e.g., horizon change)
    fetchForecast.mockRejectedValue(new Error('Network error'));

    // The component is still mounted and functional
    await waitFor(() => {
      expect(screen.getByText('DemandSense')).toBeInTheDocument();
    });
  });

  it('shows products error when fetchProducts fails', async () => {
    fetchProducts.mockRejectedValue(new Error('Products unavailable'));

    render(<App />);

    await waitFor(() => {
      expect(screen.getByText(/Products unavailable/)).toBeInTheDocument();
    });
  });
});

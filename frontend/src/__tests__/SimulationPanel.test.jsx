/**
 * SimulationPanel unit tests
 *
 * Follows the same Jest + React Testing Library pattern as the other
 * __tests__/ files in this project.
 */

jest.mock('../api/client');

// Mock Recharts — it uses browser layout APIs unavailable in jsdom
jest.mock('recharts', () => {
  const React = require('react');
  return {
    ResponsiveContainer: ({ children }) => (
      <div data-testid="responsive-container">{children}</div>
    ),
    AreaChart: ({ children }) => <div data-testid="area-chart">{children}</div>,
    Area: () => null,
    XAxis: () => null,
    YAxis: () => null,
    CartesianGrid: () => null,
    Tooltip: () => null,
    ReferenceLine: () => null,
  };
});

import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { fetchSimulationData, fetchInventory } from '../api/client';
import SimulationPanel from '../components/SimulationPanel';

// ---------------------------------------------------------------------------
// Shared test data
// ---------------------------------------------------------------------------

const MOCK_SIM_DATA = {
  product_id: 'TEST01',
  total_days: 5,
  data: [
    { date: '2020-01-01', actual_quantity: 10 },
    { date: '2020-01-02', actual_quantity: 12 },
    { date: '2020-01-03', actual_quantity: 8 },
    { date: '2020-01-04', actual_quantity: 15 },
    { date: '2020-01-05', actual_quantity: 11 },
  ],
};

const MOCK_INVENTORY_RESULT = {
  product_id: 'TEST01',
  forecasted_demand: 56.0,
  safety_stock: 20.0,
  reorder_point: 76.0,
  current_stock: 500.0,
  suggested_order: 0.0,
  status: 'SUFFICIENT',
  reorder_alert: false,
};

beforeEach(() => {
  jest.clearAllMocks();
  jest.useFakeTimers();
});

afterEach(() => {
  jest.useRealTimers();
});

// ---------------------------------------------------------------------------
// Helper: render with a selected product and resolved simulation data
// ---------------------------------------------------------------------------

async function renderWithData(productId = 'TEST01') {
  fetchSimulationData.mockResolvedValue(MOCK_SIM_DATA);
  const utils = render(<SimulationPanel selectedProduct={productId} />);
  // Wait for data to load
  await waitFor(() => {
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });
  return utils;
}

// ---------------------------------------------------------------------------
// Test: renders setup panel when simStatus is idle
// ---------------------------------------------------------------------------

describe('SimulationPanel — idle / setup panel', () => {
  it('renders setup panel with inputs when simStatus is idle', async () => {
    await renderWithData();
    expect(screen.getByLabelText(/initial stock/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/lead time/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /start simulation/i })).toBeInTheDocument();
  });

  it('shows section header "Inventory Simulation"', async () => {
    await renderWithData();
    expect(screen.getByText('Inventory Simulation')).toBeInTheDocument();
  });

  it('shows available days count after data loads', async () => {
    await renderWithData();
    expect(screen.getByText(/5 days of historical data/i)).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Test: Start Simulation button disabled when inputs empty
// ---------------------------------------------------------------------------

describe('SimulationPanel — Start Simulation button', () => {
  it('is disabled when initial stock is empty', async () => {
    await renderWithData();
    // Lead time has a default value of 7, but initial stock is empty
    expect(
      screen.getByRole('button', { name: /start simulation/i })
    ).toBeDisabled();
  });

  it('is enabled when both inputs are filled', async () => {
    await renderWithData();
    fireEvent.change(screen.getByLabelText(/initial stock/i), {
      target: { value: '1000' },
    });
    expect(
      screen.getByRole('button', { name: /start simulation/i })
    ).not.toBeDisabled();
  });

  it('is disabled when no product is selected', () => {
    fetchSimulationData.mockResolvedValue(MOCK_SIM_DATA);
    render(<SimulationPanel selectedProduct={null} />);
    // No setup form shown — just the "select a product" message
    expect(
      screen.queryByRole('button', { name: /start simulation/i })
    ).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Test: shows playback controls after simulation starts
// ---------------------------------------------------------------------------

describe('SimulationPanel — playback controls', () => {
  async function startSim() {
    await renderWithData();
    fireEvent.change(screen.getByLabelText(/initial stock/i), {
      target: { value: '500' },
    });
    fireEvent.click(screen.getByRole('button', { name: /start simulation/i }));
  }

  it('shows Play/Pause button after simulation starts', async () => {
    await startSim();
    // Should show Pause since it starts playing
    expect(screen.getByRole('button', { name: /pause simulation/i })).toBeInTheDocument();
  });

  it('shows Reset button after simulation starts', async () => {
    await startSim();
    expect(screen.getByRole('button', { name: /reset simulation/i })).toBeInTheDocument();
  });

  it('shows speed selector buttons', async () => {
    await startSim();
    expect(screen.getByRole('button', { name: /slow/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /normal/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /fast/i })).toBeInTheDocument();
  });

  it('shows Place Order button after simulation starts', async () => {
    await startSim();
    expect(screen.getByRole('button', { name: /place order/i })).toBeInTheDocument();
  });

  it('hides setup panel after simulation starts', async () => {
    await startSim();
    expect(
      screen.queryByRole('button', { name: /start simulation/i })
    ).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Test: Place Order button disabled while pendingRestock is not null
// ---------------------------------------------------------------------------

describe('SimulationPanel — Place Order button', () => {
  async function startAndPause() {
    fetchInventory.mockResolvedValue(MOCK_INVENTORY_RESULT);
    await renderWithData();
    fireEvent.change(screen.getByLabelText(/initial stock/i), {
      target: { value: '500' },
    });
    fireEvent.click(screen.getByRole('button', { name: /start simulation/i }));
    // Pause immediately
    fireEvent.click(screen.getByRole('button', { name: /pause simulation/i }));
  }

  it('is enabled when no order is in transit', async () => {
    await startAndPause();
    expect(screen.getByRole('button', { name: /place order/i })).not.toBeDisabled();
  });

  it('is disabled while an order is in transit', async () => {
    await startAndPause();
    // Place an order
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /place order/i }));
    });
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /place order/i })).toBeDisabled();
    });
  });

  it('shows "Order in transit" message after placing order', async () => {
    await startAndPause();
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /place order/i }));
    });
    await waitFor(() => {
      expect(screen.getByText(/order in transit/i)).toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// Test: Reset button returns to idle state
// ---------------------------------------------------------------------------

describe('SimulationPanel — Reset button', () => {
  it('returns to idle state and shows setup panel again', async () => {
    await renderWithData();
    fireEvent.change(screen.getByLabelText(/initial stock/i), {
      target: { value: '500' },
    });
    fireEvent.click(screen.getByRole('button', { name: /start simulation/i }));

    // Verify we're in running state
    expect(screen.getByRole('button', { name: /pause simulation/i })).toBeInTheDocument();

    // Reset
    fireEvent.click(screen.getByRole('button', { name: /reset simulation/i }));

    // Should be back to idle
    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /start simulation/i })
      ).toBeInTheDocument();
    });
  });

  it('clears the initial stock input on reset', async () => {
    await renderWithData();
    fireEvent.change(screen.getByLabelText(/initial stock/i), {
      target: { value: '500' },
    });
    fireEvent.click(screen.getByRole('button', { name: /start simulation/i }));
    fireEvent.click(screen.getByRole('button', { name: /reset simulation/i }));

    await waitFor(() => {
      expect(screen.getByLabelText(/initial stock/i)).toHaveValue(null);
    });
  });
});

// ---------------------------------------------------------------------------
// Test: shows SkeletonLoader while loading historical data
// ---------------------------------------------------------------------------

describe('SimulationPanel — loading state', () => {
  it('shows skeleton loader while fetching simulation data', () => {
    // Keep the promise pending
    fetchSimulationData.mockReturnValue(new Promise(() => {}));
    render(<SimulationPanel selectedProduct="TEST01" />);
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('hides skeleton after data loads', async () => {
    fetchSimulationData.mockResolvedValue(MOCK_SIM_DATA);
    render(<SimulationPanel selectedProduct="TEST01" />);
    await waitFor(() => {
      expect(screen.queryByRole('status')).not.toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// Test: shows ErrorMessage when API fails
// ---------------------------------------------------------------------------

describe('SimulationPanel — error state', () => {
  it('shows error message when fetchSimulationData fails', async () => {
    fetchSimulationData.mockRejectedValue(new Error('Network error'));
    render(<SimulationPanel selectedProduct="TEST01" />);
    await waitFor(() => {
      expect(screen.getByText(/failed to load simulation data/i)).toBeInTheDocument();
    });
  });

  it('shows the specific error message', async () => {
    fetchSimulationData.mockRejectedValue(new Error('Product not found'));
    render(<SimulationPanel selectedProduct="TEST01" />);
    await waitFor(() => {
      expect(screen.getByText(/product not found/i)).toBeInTheDocument();
    });
  });

  it('does not show setup panel when there is an error', async () => {
    fetchSimulationData.mockRejectedValue(new Error('Server error'));
    render(<SimulationPanel selectedProduct="TEST01" />);
    await waitFor(() => {
      expect(
        screen.queryByRole('button', { name: /start simulation/i })
      ).not.toBeInTheDocument();
    });
  });
});

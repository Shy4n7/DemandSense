/**
 * InventoryPanel unit tests
 *
 * Follows the same Jest + React Testing Library pattern as the other
 * __tests__/ files in this project.
 */

jest.mock('../api/client');

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { fetchInventory } from '../api/client';
import InventoryPanel from '../components/InventoryPanel';

// ---------------------------------------------------------------------------
// Shared test data
// ---------------------------------------------------------------------------

const SUFFICIENT_RESULT = {
  product_id: 'TEST01',
  forecasted_demand: 700.0,
  safety_stock: 0.0,
  reorder_point: 700.0,
  current_stock: 2000.0,
  suggested_order: 0.0,
  status: 'SUFFICIENT',
  reorder_alert: false,
};

const REORDER_NOW_RESULT = {
  ...SUFFICIENT_RESULT,
  current_stock: 700.0,
  suggested_order: 0.0,
  status: 'REORDER NOW',
  reorder_alert: true,
};

const CRITICAL_RESULT = {
  ...SUFFICIENT_RESULT,
  current_stock: 10.0,
  suggested_order: 690.0,
  status: 'CRITICAL',
  reorder_alert: true,
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fillAndSubmit({ stock = '2000', lead = '14', sl = '0.95' } = {}) {
  fireEvent.change(screen.getByLabelText(/current stock/i), {
    target: { value: stock },
  });
  fireEvent.change(screen.getByLabelText(/lead time/i), {
    target: { value: lead },
  });
  fireEvent.change(screen.getByLabelText(/service level/i), {
    target: { value: sl },
  });
  fireEvent.click(screen.getByRole('button', { name: /calculate/i }));
}

beforeEach(() => {
  jest.clearAllMocks();
});

// ---------------------------------------------------------------------------
// Test: renders input fields
// ---------------------------------------------------------------------------

describe('InventoryPanel — input fields', () => {
  it('renders current stock input', () => {
    render(<InventoryPanel selectedProduct="TEST01" />);
    expect(screen.getByLabelText(/current stock/i)).toBeInTheDocument();
  });

  it('renders lead time input', () => {
    render(<InventoryPanel selectedProduct="TEST01" />);
    expect(screen.getByLabelText(/lead time/i)).toBeInTheDocument();
  });

  it('renders service level select with 90%, 95%, 99% options', () => {
    render(<InventoryPanel selectedProduct="TEST01" />);
    const select = screen.getByLabelText(/service level/i);
    expect(select).toBeInTheDocument();
    expect(screen.getByRole('option', { name: '90%' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: '95%' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: '99%' })).toBeInTheDocument();
  });

  it('renders Calculate button', () => {
    render(<InventoryPanel selectedProduct="TEST01" />);
    expect(screen.getByRole('button', { name: /calculate/i })).toBeInTheDocument();
  });

  it('disables Calculate button when no product is selected', () => {
    render(<InventoryPanel selectedProduct={null} />);
    expect(screen.getByRole('button', { name: /calculate/i })).toBeDisabled();
  });

  it('enables Calculate button when a product is selected', () => {
    render(<InventoryPanel selectedProduct="TEST01" />);
    expect(screen.getByRole('button', { name: /calculate/i })).not.toBeDisabled();
  });
});

// ---------------------------------------------------------------------------
// Test: shows skeleton while loading
// ---------------------------------------------------------------------------

describe('InventoryPanel — loading state', () => {
  it('shows skeleton loader while API call is in flight', async () => {
    // Keep the promise pending so we can observe the loading state
    fetchInventory.mockReturnValue(new Promise(() => {}));

    render(<InventoryPanel selectedProduct="TEST01" />);
    fillAndSubmit();

    // SkeletonLoader renders role="status"
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('hides skeleton after API resolves', async () => {
    fetchInventory.mockResolvedValue(SUFFICIENT_RESULT);

    render(<InventoryPanel selectedProduct="TEST01" />);
    fillAndSubmit();

    await waitFor(() => {
      expect(screen.queryByRole('status')).not.toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// Test: displays SUFFICIENT badge on success
// ---------------------------------------------------------------------------

describe('InventoryPanel — SUFFICIENT result', () => {
  it('displays SUFFICIENT status badge', async () => {
    fetchInventory.mockResolvedValue(SUFFICIENT_RESULT);

    render(<InventoryPanel selectedProduct="TEST01" />);
    fillAndSubmit();

    await waitFor(() => {
      expect(screen.getByText('SUFFICIENT')).toBeInTheDocument();
    });
  });

  it('does NOT show reorder alert banner when status is SUFFICIENT', async () => {
    fetchInventory.mockResolvedValue(SUFFICIENT_RESULT);

    render(<InventoryPanel selectedProduct="TEST01" />);
    fillAndSubmit();

    await waitFor(() => {
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    });
  });

  it('shows forecasted demand, safety stock, and reorder point tiles', async () => {
    fetchInventory.mockResolvedValue(SUFFICIENT_RESULT);

    render(<InventoryPanel selectedProduct="TEST01" />);
    fillAndSubmit();

    await waitFor(() => {
      // Each label appears at least once in the results tiles
      // (some also appear in the subtitle, so use getAllByText)
      expect(screen.getAllByText(/forecasted demand/i).length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText(/safety stock/i).length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText(/reorder point/i).length).toBeGreaterThanOrEqual(1);
    });
  });
});

// ---------------------------------------------------------------------------
// Test: displays red banner when reorder_alert is true
// ---------------------------------------------------------------------------

describe('InventoryPanel — reorder alert banner', () => {
  it('shows red alert banner when reorder_alert is true (REORDER NOW)', async () => {
    fetchInventory.mockResolvedValue(REORDER_NOW_RESULT);

    render(<InventoryPanel selectedProduct="TEST01" />);
    fillAndSubmit();

    await waitFor(() => {
      const alert = screen.getByRole('alert');
      expect(alert).toBeInTheDocument();
      expect(alert).toHaveTextContent(/reorder/i);
    });
  });

  it('shows red alert banner when status is CRITICAL', async () => {
    fetchInventory.mockResolvedValue(CRITICAL_RESULT);

    render(<InventoryPanel selectedProduct="TEST01" />);
    fillAndSubmit();

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByText('CRITICAL')).toBeInTheDocument();
    });
  });

  it('banner mentions the suggested order quantity', async () => {
    fetchInventory.mockResolvedValue(CRITICAL_RESULT);

    render(<InventoryPanel selectedProduct="TEST01" />);
    fillAndSubmit();

    await waitFor(() => {
      const alert = screen.getByRole('alert');
      // suggested_order = 690 → should appear in the banner text
      expect(alert).toHaveTextContent('690');
    });
  });
});

// ---------------------------------------------------------------------------
// Test: shows ErrorMessage on API failure
// ---------------------------------------------------------------------------

describe('InventoryPanel — error state', () => {
  it('shows error message when API call fails', async () => {
    fetchInventory.mockRejectedValue(new Error('Service unavailable'));

    render(<InventoryPanel selectedProduct="TEST01" />);
    fillAndSubmit();

    await waitFor(() => {
      expect(
        screen.getByText(/failed to load inventory data/i)
      ).toBeInTheDocument();
    });
  });

  it('shows the specific error message from the API', async () => {
    fetchInventory.mockRejectedValue(new Error('Product not found'));

    render(<InventoryPanel selectedProduct="TEST01" />);
    fillAndSubmit();

    await waitFor(() => {
      expect(screen.getByText(/product not found/i)).toBeInTheDocument();
    });
  });

  it('does not show results when there is an error', async () => {
    fetchInventory.mockRejectedValue(new Error('Network error'));

    render(<InventoryPanel selectedProduct="TEST01" />);
    fillAndSubmit();

    await waitFor(() => {
      expect(screen.queryByText('SUFFICIENT')).not.toBeInTheDocument();
      expect(screen.queryByText('REORDER NOW')).not.toBeInTheDocument();
      expect(screen.queryByText('CRITICAL')).not.toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// Test: calls fetchInventory with correct arguments
// ---------------------------------------------------------------------------

describe('InventoryPanel — API call arguments', () => {
  it('calls fetchInventory with the selected product, stock, lead time, and service level', async () => {
    fetchInventory.mockResolvedValue(SUFFICIENT_RESULT);

    render(<InventoryPanel selectedProduct="85123A" />);
    fillAndSubmit({ stock: '500', lead: '21', sl: '0.99' });

    await waitFor(() => {
      expect(fetchInventory).toHaveBeenCalledWith('85123A', 500, 21, 0.99);
    });
  });
});

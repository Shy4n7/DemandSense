/**
 * Task 17.2 — AnomalyTable unit tests (updated for retailer-friendly redesign).
 */

import { render, screen, fireEvent, within } from '@testing-library/react';
import AnomalyTable from '../components/AnomalyTable';

/** Click a filter chip button by its label text, scoped to the filter group. */
function clickFilterChip(label) {
  const group = screen.getByRole('group', { name: 'Filter anomalies' });
  fireEvent.click(within(group).getByText(label));
}

const ANOMALIES = [
  {
    date: '2024-01-10',
    quantity: 500,
    unit_price: 9.99,
    anomaly_score: -0.25,   // red (< -0.1)
    is_anomaly: true,
    reason: 'demand_spike',
  },
  {
    date: '2024-01-11',
    quantity: 200,
    unit_price: 15.0,
    anomaly_score: -0.05,   // amber (-0.1 <= score <= 0.0)
    is_anomaly: true,
    reason: 'price_anomaly',
  },
  {
    date: '2024-01-12',
    quantity: 0,
    unit_price: 9.99,
    anomaly_score: -0.08,   // amber
    is_anomaly: true,
    reason: 'stockout_signal',
  },
  {
    date: '2024-01-13',
    quantity: 150,
    unit_price: 10.0,
    anomaly_score: 0.1,     // no highlight (> 0.0)
    is_anomaly: false,
    reason: 'demand_spike',
  },
];

describe('AnomalyTable', () => {
  describe('filter chips', () => {
    it('shows all rows when "All" filter is active (default)', () => {
      render(<AnomalyTable anomalies={ANOMALIES} />);
      // All four dates should be visible via test ID
      expect(screen.getByTestId('anomaly-card-2024-01-10')).toBeInTheDocument();
      expect(screen.getByTestId('anomaly-card-2024-01-11')).toBeInTheDocument();
      expect(screen.getByTestId('anomaly-card-2024-01-12')).toBeInTheDocument();
      expect(screen.getByTestId('anomaly-card-2024-01-13')).toBeInTheDocument();
    });

    it('filters to only demand_spike rows when "Demand Spike" chip is clicked', () => {
      render(<AnomalyTable anomalies={ANOMALIES} />);
      clickFilterChip('Demand Spike');
      expect(screen.getByTestId('anomaly-card-2024-01-10')).toBeInTheDocument();
      expect(screen.getByTestId('anomaly-card-2024-01-13')).toBeInTheDocument();
      expect(screen.queryByTestId('anomaly-card-2024-01-11')).not.toBeInTheDocument();
      expect(screen.queryByTestId('anomaly-card-2024-01-12')).not.toBeInTheDocument();
    });

    it('filters to only price_anomaly rows when "Price Anomaly" chip is clicked', () => {
      render(<AnomalyTable anomalies={ANOMALIES} />);
      clickFilterChip('Price Anomaly');
      expect(screen.getByTestId('anomaly-card-2024-01-11')).toBeInTheDocument();
      expect(screen.queryByTestId('anomaly-card-2024-01-10')).not.toBeInTheDocument();
      expect(screen.queryByTestId('anomaly-card-2024-01-12')).not.toBeInTheDocument();
      expect(screen.queryByTestId('anomaly-card-2024-01-13')).not.toBeInTheDocument();
    });

    it('filters to only stockout_signal rows when "Stockout Signal" chip is clicked', () => {
      render(<AnomalyTable anomalies={ANOMALIES} />);
      clickFilterChip('Stockout Signal');
      expect(screen.getByTestId('anomaly-card-2024-01-12')).toBeInTheDocument();
      expect(screen.queryByTestId('anomaly-card-2024-01-10')).not.toBeInTheDocument();
      expect(screen.queryByTestId('anomaly-card-2024-01-11')).not.toBeInTheDocument();
      expect(screen.queryByTestId('anomaly-card-2024-01-13')).not.toBeInTheDocument();
    });

    it('returns to showing all rows when "All" chip is clicked after filtering', () => {
      render(<AnomalyTable anomalies={ANOMALIES} />);
      clickFilterChip('Demand Spike');
      clickFilterChip('All');
      expect(screen.getByTestId('anomaly-card-2024-01-10')).toBeInTheDocument();
      expect(screen.getByTestId('anomaly-card-2024-01-11')).toBeInTheDocument();
      expect(screen.getByTestId('anomaly-card-2024-01-12')).toBeInTheDocument();
      expect(screen.getByTestId('anomaly-card-2024-01-13')).toBeInTheDocument();
    });
  });

  describe('row highlighting', () => {
    it('applies red background class to rows with anomaly_score < -0.1', () => {
      render(<AnomalyTable anomalies={ANOMALIES} />);
      const redCard = screen.getByTestId('anomaly-card-2024-01-10');
      expect(redCard).toBeDefined();
      expect(redCard.className).toContain('bg-red-950/20');
    });

    it('applies amber background class to rows with -0.1 <= anomaly_score <= 0.0', () => {
      render(<AnomalyTable anomalies={ANOMALIES} />);
      const amberCard = screen.getByTestId('anomaly-card-2024-01-11');
      expect(amberCard).toBeDefined();
      expect(amberCard.className).toContain('bg-amber-950/20');
    });

    it('applies no highlight class to rows with anomaly_score > 0.0', () => {
      render(<AnomalyTable anomalies={ANOMALIES} />);
      const normalCard = screen.getByTestId('anomaly-card-2024-01-13');
      expect(normalCard).toBeDefined();
      expect(normalCard.className).not.toContain('bg-red-950/20');
      expect(normalCard.className).not.toContain('bg-amber-950/20');
    });
  });

  describe('empty state', () => {
    it('displays empty state message when anomalies array is empty', () => {
      render(<AnomalyTable anomalies={[]} />);
      expect(
        screen.getByText('No anomalies detected for this product.')
      ).toBeInTheDocument();
    });

    it('displays empty state message when filter produces no results', () => {
      // Only demand_spike rows; filter by price_anomaly → empty
      render(
        <AnomalyTable
          anomalies={[
            {
              date: '2024-01-10',
              quantity: 500,
              unit_price: 9.99,
              anomaly_score: -0.25,
              is_anomaly: true,
              reason: 'demand_spike',
            },
          ]}
        />
      );
      fireEvent.click(within(screen.getByRole('group', { name: 'Filter anomalies' })).getByText('Price Anomaly'));
      expect(
        screen.getByText('No anomalies detected for this product.')
      ).toBeInTheDocument();
    });
  });

  describe('loading and error states', () => {
    it('renders skeleton loader while loading is true', () => {
      render(<AnomalyTable anomalies={null} loading={true} />);
      expect(screen.getByRole('status')).toBeInTheDocument();
    });

    it('renders error message when error prop is set', () => {
      render(<AnomalyTable anomalies={null} error="Failed to fetch" />);
      expect(screen.getByText(/Failed to load anomaly data/)).toBeInTheDocument();
    });
  });
});

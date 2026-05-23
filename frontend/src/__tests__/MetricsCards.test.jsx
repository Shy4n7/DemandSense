/**
 * MetricsCards unit tests — updated for the retailer-friendly redesign.
 *
 * The component now shows 3 cards:
 *   1. Expected Sales — from forecast
 *   2. Stock Status   — from inventory API (status badge + suggested order text)
 *   3. Price & Stock Alerts — from anomalies
 */

import { render, screen } from '@testing-library/react';
import MetricsCards from '../components/MetricsCards';

const FORECAST = { forecast: [{ predicted: 10 }, { predicted: 25 }] };
const ANOMALIES = { total_anomalies: 3 };
const INVENTORY_SUFFICIENT = {
  product_id: 'P001', forecasted_demand: 35, safety_stock: 10,
  reorder_point: 45, current_stock: 100, suggested_order: 0,
  status: 'SUFFICIENT', reorder_alert: false,
};
const INVENTORY_CRITICAL = {
  product_id: 'P001', forecasted_demand: 35, safety_stock: 10,
  reorder_point: 45, current_stock: 5, suggested_order: 40,
  status: 'CRITICAL', reorder_alert: true,
};
const INVENTORY_REORDER = {
  product_id: 'P001', forecasted_demand: 35, safety_stock: 10,
  reorder_point: 45, current_stock: 30, suggested_order: 15,
  status: 'REORDER NOW', reorder_alert: true,
};

describe('MetricsCards', () => {
  it('shows "N/A" for Expected Sales when forecast is null', () => {
    render(
      <MetricsCards
        forecast={null}
        anomalies={null}
        inventory={null}
        loadingForecast={false}
        loadingAnomalies={false}
        loadingInventory={false}
      />
    );
    const naElements = screen.getAllByText('N/A');
    expect(naElements.length).toBeGreaterThanOrEqual(1);
  });

  it('renders skeleton loaders while loadingForecast is true', () => {
    render(
      <MetricsCards
        forecast={null}
        anomalies={null}
        inventory={null}
        loadingForecast={true}
        loadingAnomalies={false}
        loadingInventory={false}
      />
    );
    const loaders = screen.getAllByRole('status');
    expect(loaders.length).toBeGreaterThanOrEqual(1);
  });

  it('renders skeleton loaders while loadingAnomalies is true', () => {
    render(
      <MetricsCards
        forecast={null}
        anomalies={null}
        inventory={null}
        loadingForecast={false}
        loadingAnomalies={true}
        loadingInventory={false}
      />
    );
    const loaders = screen.getAllByRole('status');
    expect(loaders.length).toBeGreaterThanOrEqual(1);
  });

  it('renders skeleton loaders while loadingInventory is true', () => {
    render(
      <MetricsCards
        forecast={null}
        anomalies={null}
        inventory={null}
        loadingForecast={false}
        loadingAnomalies={false}
        loadingInventory={true}
      />
    );
    const loaders = screen.getAllByRole('status');
    expect(loaders.length).toBeGreaterThanOrEqual(1);
  });

  it('shows error indicator when errorForecast is set', () => {
    render(
      <MetricsCards
        forecast={null}
        anomalies={null}
        inventory={null}
        loadingForecast={false}
        loadingAnomalies={false}
        loadingInventory={false}
        errorForecast="Service unavailable"
      />
    );
    const alerts = screen.getAllByRole('alert');
    expect(alerts.length).toBeGreaterThanOrEqual(1);
    expect(alerts[0]).toHaveTextContent('Service unavailable');
  });

  it('shows error indicator when errorAnomalies is set', () => {
    render(
      <MetricsCards
        forecast={null}
        anomalies={null}
        inventory={null}
        loadingForecast={false}
        loadingAnomalies={false}
        loadingInventory={false}
        errorAnomalies="Anomaly service down"
      />
    );
    const alerts = screen.getAllByRole('alert');
    expect(alerts.length).toBeGreaterThanOrEqual(1);
    expect(alerts[0]).toHaveTextContent('Anomaly service down');
  });

  it('renders expected demand value in quantity mode', () => {
    render(
      <MetricsCards
        forecast={FORECAST}
        anomalies={ANOMALIES}
        inventory={INVENTORY_SUFFICIENT}
        loadingForecast={false}
        loadingAnomalies={false}
        loadingInventory={false}
        unitPrice={5.0}
        yAxisUnit="quantity"
      />
    );
    expect(screen.getByText('35 units')).toBeInTheDocument();
  });

  it('renders expected demand value in revenue mode', () => {
    render(
      <MetricsCards
        forecast={FORECAST}
        anomalies={ANOMALIES}
        inventory={INVENTORY_SUFFICIENT}
        loadingForecast={false}
        loadingAnomalies={false}
        loadingInventory={false}
        unitPrice={5.0}
        yAxisUnit="revenue"
      />
    );
    expect(screen.getByText('₹175')).toBeInTheDocument();
  });

  it('shows STOCK OK badge when inventory status is SUFFICIENT', () => {
    render(
      <MetricsCards
        forecast={null}
        anomalies={null}
        inventory={INVENTORY_SUFFICIENT}
        loadingForecast={false}
        loadingAnomalies={false}
        loadingInventory={false}
      />
    );
    expect(screen.getByText('STOCK OK')).toBeInTheDocument();
  });

  it('shows ORDER SOON badge when inventory status is REORDER NOW', () => {
    render(
      <MetricsCards
        forecast={null}
        anomalies={null}
        inventory={INVENTORY_REORDER}
        loadingForecast={false}
        loadingAnomalies={false}
        loadingInventory={false}
      />
    );
    expect(screen.getByText('ORDER SOON')).toBeInTheDocument();
  });

  it('shows CRITICAL badge when inventory status is CRITICAL', () => {
    render(
      <MetricsCards
        forecast={null}
        anomalies={null}
        inventory={INVENTORY_CRITICAL}
        loadingForecast={false}
        loadingAnomalies={false}
        loadingInventory={false}
      />
    );
    expect(screen.getByText('CRITICAL')).toBeInTheDocument();
  });

  it('shows All Clear when there are zero anomalies', () => {
    render(
      <MetricsCards
        forecast={null}
        anomalies={{ total_anomalies: 0 }}
        inventory={null}
        loadingForecast={false}
        loadingAnomalies={false}
        loadingInventory={false}
      />
    );
    expect(screen.getByText('All Clear')).toBeInTheDocument();
  });

  it('shows alert count when there are anomalies', () => {
    render(
      <MetricsCards
        forecast={null}
        anomalies={ANOMALIES}
        inventory={null}
        loadingForecast={false}
        loadingAnomalies={false}
        loadingInventory={false}
      />
    );
    expect(screen.getByText('3 Alerts')).toBeInTheDocument();
  });
});

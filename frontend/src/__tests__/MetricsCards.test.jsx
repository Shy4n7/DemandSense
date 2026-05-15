/**
 * Task 15.2 — MetricsCards unit tests
 */

import { render, screen } from '@testing-library/react';
import MetricsCards from '../components/MetricsCards';

describe('MetricsCards', () => {
  it('shows "N/A" for MAPE and RMSE when forecast is null', () => {
    render(
      <MetricsCards
        forecast={null}
        anomalies={null}
        loadingForecast={false}
        loadingAnomalies={false}
      />
    );
    // Both MAPE and RMSE cards should show N/A
    const naElements = screen.getAllByText('N/A');
    expect(naElements.length).toBeGreaterThanOrEqual(2);
  });

  it('renders skeleton loaders while loadingForecast is true', () => {
    render(
      <MetricsCards
        forecast={null}
        anomalies={null}
        loadingForecast={true}
        loadingAnomalies={false}
      />
    );
    // SkeletonLoader renders role="status" with aria-label="Loading"
    const loaders = screen.getAllByRole('status');
    expect(loaders.length).toBeGreaterThanOrEqual(1);
  });

  it('renders skeleton loaders while loadingAnomalies is true', () => {
    render(
      <MetricsCards
        forecast={null}
        anomalies={null}
        loadingForecast={false}
        loadingAnomalies={true}
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
        loadingForecast={false}
        loadingAnomalies={false}
        errorForecast="Service unavailable"
      />
    );
    // MetricCard renders an alert role paragraph for errors
    const alerts = screen.getAllByRole('alert');
    expect(alerts.length).toBeGreaterThanOrEqual(1);
    expect(alerts[0]).toHaveTextContent('Service unavailable');
  });

  it('shows error indicator when errorAnomalies is set', () => {
    render(
      <MetricsCards
        forecast={null}
        anomalies={null}
        loadingForecast={false}
        loadingAnomalies={false}
        errorAnomalies="Anomaly service down"
      />
    );
    const alerts = screen.getAllByRole('alert');
    expect(alerts.length).toBeGreaterThanOrEqual(1);
    expect(alerts[0]).toHaveTextContent('Anomaly service down');
  });

  it('renders MAPE and RMSE values when forecast data is provided', () => {
    render(
      <MetricsCards
        forecast={{ metrics: { mape: 5.25, rmse: 12.3 } }}
        anomalies={{ total_anomalies: 3 }}
        loadingForecast={false}
        loadingAnomalies={false}
      />
    );
    expect(screen.getByText('5.25%')).toBeInTheDocument();
    expect(screen.getByText('12.30')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
  });
});

/**
 * Task 16.2 — ForecastChart unit tests
 *
 * Recharts components are mocked because they rely on browser layout APIs
 * (ResizeObserver, SVG measurements) that are unavailable in jsdom.
 */

jest.mock('recharts', () => {
  const React = require('react');
  return {
    ResponsiveContainer: ({ children }) => (
      <div data-testid="responsive-container">{children}</div>
    ),
    ComposedChart: ({ children }) => (
      <div data-testid="composed-chart">{children}</div>
    ),
    Line: () => null,
    Area: () => null,
    XAxis: () => null,
    YAxis: () => null,
    CartesianGrid: () => null,
    Tooltip: () => null,
    Legend: () => null,
  };
});

import { render, screen } from '@testing-library/react';
import ForecastChart from '../components/ForecastChart';

const SAMPLE_FORECAST = {
  forecast: [
    { date: '2024-01-15', predicted: 100, lower: 80, upper: 120 },
    { date: '2024-01-16', predicted: 110, lower: 90, upper: 130 },
  ],
  metrics: { mape: 4.5, rmse: 10.2 },
};

const SAMPLE_HISTORY = [
  { date: '2024-01-10', quantity: 95 },
  { date: '2024-01-11', quantity: 102 },
];

describe('ForecastChart', () => {
  it('renders skeleton loader while loading is true', () => {
    render(
      <ForecastChart
        forecast={null}
        history={[]}
        loading={true}
        error={null}
        horizon={14}
        onHorizonChange={jest.fn()}
      />
    );
    expect(screen.getByRole('status')).toBeInTheDocument();
    expect(screen.queryByTestId('composed-chart')).not.toBeInTheDocument();
  });

  it('renders error message when error is set', () => {
    render(
      <ForecastChart
        forecast={null}
        history={[]}
        loading={false}
        error="Forecast service failed"
        horizon={14}
        onHorizonChange={jest.fn()}
      />
    );
    expect(screen.getByText(/Forecast service failed/)).toBeInTheDocument();
    expect(screen.queryByTestId('composed-chart')).not.toBeInTheDocument();
  });

  it('renders chart container when forecast data is available', () => {
    render(
      <ForecastChart
        forecast={SAMPLE_FORECAST}
        history={SAMPLE_HISTORY}
        loading={false}
        error={null}
        horizon={14}
        onHorizonChange={jest.fn()}
      />
    );
    expect(screen.getByTestId('composed-chart')).toBeInTheDocument();
  });

  it('renders chart even with empty forecast array', () => {
    render(
      <ForecastChart
        forecast={{ forecast: [], metrics: {} }}
        history={[]}
        loading={false}
        error={null}
        horizon={14}
        onHorizonChange={jest.fn()}
      />
    );
    expect(screen.getByTestId('composed-chart')).toBeInTheDocument();
  });

  it('shows the "Demand Forecast" heading when not loading or errored', () => {
    render(
      <ForecastChart
        forecast={SAMPLE_FORECAST}
        history={SAMPLE_HISTORY}
        loading={false}
        error={null}
        horizon={14}
        onHorizonChange={jest.fn()}
      />
    );
    expect(screen.getByText('Demand Forecast')).toBeInTheDocument();
  });
});

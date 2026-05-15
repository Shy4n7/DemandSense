/**
 * Task 18.2 — FeatureImportance unit tests
 *
 * Recharts is mocked because it relies on browser layout APIs unavailable in jsdom.
 */

jest.mock('recharts', () => {
  const React = require('react');
  return {
    ResponsiveContainer: ({ children }) => (
      <div data-testid="responsive-container">{children}</div>
    ),
    BarChart: ({ children }) => (
      <div data-testid="bar-chart">{children}</div>
    ),
    Bar: () => null,
    XAxis: () => null,
    YAxis: () => null,
    CartesianGrid: () => null,
    Tooltip: () => null,
    Cell: () => null,
    LabelList: () => null,
  };
});

import { render, screen } from '@testing-library/react';
import FeatureImportance from '../components/FeatureImportance';

const FEATURES = [
  { name: 'lag_7', importance: 0.35 },
  { name: 'price', importance: 0.25 },
  { name: 'day_of_week', importance: 0.15 },
];

describe('FeatureImportance', () => {
  it('shows error message when features array is empty', () => {
    render(
      <FeatureImportance importance={{ features: [] }} loading={false} error={null} />
    );
    expect(
      screen.getByText('No feature importance data available for this product.')
    ).toBeInTheDocument();
    expect(screen.queryByTestId('bar-chart')).not.toBeInTheDocument();
  });

  it('shows error message when importance is null (no data)', () => {
    render(
      <FeatureImportance importance={null} loading={false} error={null} />
    );
    expect(
      screen.getByText('No feature importance data available for this product.')
    ).toBeInTheDocument();
  });

  it('shows error message when error prop is set', () => {
    render(
      <FeatureImportance
        importance={null}
        loading={false}
        error="Importance service unavailable"
      />
    );
    expect(
      screen.getByText(/Failed to load feature importance data/)
    ).toBeInTheDocument();
    expect(screen.queryByTestId('bar-chart')).not.toBeInTheDocument();
  });

  it('renders the bar chart when features are provided', () => {
    render(
      <FeatureImportance
        importance={{ features: FEATURES }}
        loading={false}
        error={null}
      />
    );
    expect(screen.getByTestId('bar-chart')).toBeInTheDocument();
  });

  it('renders skeleton loader while loading is true', () => {
    render(
      <FeatureImportance importance={null} loading={true} error={null} />
    );
    expect(screen.getByRole('status')).toBeInTheDocument();
    expect(screen.queryByTestId('bar-chart')).not.toBeInTheDocument();
  });
});

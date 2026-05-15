/**
 * Task 14.2 — ProductSelector unit tests
 */

import { render, screen, fireEvent } from '@testing-library/react';
import ProductSelector from '../components/ProductSelector';

const PRODUCTS = [
  { product_id: 'P001', description: 'Widget Alpha' },
  { product_id: 'P002', description: 'Gadget Beta' },
  { product_id: 'P003', description: 'Doohickey Gamma' },
];

describe('ProductSelector', () => {
  it('renders the search input', () => {
    render(
      <ProductSelector
        products={PRODUCTS}
        selectedProduct={null}
        onSelect={jest.fn()}
      />
    );
    expect(screen.getByRole('combobox')).toBeInTheDocument();
  });

  it('shows all products in the dropdown when opened', () => {
    render(
      <ProductSelector
        products={PRODUCTS}
        selectedProduct={null}
        onSelect={jest.fn()}
      />
    );
    fireEvent.focus(screen.getByRole('combobox'));
    expect(screen.getByText(/Widget Alpha/)).toBeInTheDocument();
    expect(screen.getByText(/Gadget Beta/)).toBeInTheDocument();
    expect(screen.getByText(/Doohickey Gamma/)).toBeInTheDocument();
  });

  it('filters products by description (name)', () => {
    render(
      <ProductSelector
        products={PRODUCTS}
        selectedProduct={null}
        onSelect={jest.fn()}
      />
    );
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'gadget' } });
    expect(screen.getByText(/Gadget Beta/)).toBeInTheDocument();
    expect(screen.queryByText(/Widget Alpha/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Doohickey Gamma/)).not.toBeInTheDocument();
  });

  it('filters products by product ID', () => {
    render(
      <ProductSelector
        products={PRODUCTS}
        selectedProduct={null}
        onSelect={jest.fn()}
      />
    );
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'P003' } });
    expect(screen.getByText(/Doohickey Gamma/)).toBeInTheDocument();
    expect(screen.queryByText(/Widget Alpha/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Gadget Beta/)).not.toBeInTheDocument();
  });

  it('shows "No products found" when filter matches nothing', () => {
    render(
      <ProductSelector
        products={PRODUCTS}
        selectedProduct={null}
        onSelect={jest.fn()}
      />
    );
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'zzz' } });
    expect(screen.getByText('No products found')).toBeInTheDocument();
  });

  it('shows error state when error prop is set', () => {
    render(
      <ProductSelector
        products={[]}
        selectedProduct={null}
        onSelect={jest.fn()}
        error="Network error"
      />
    );
    expect(screen.getByText(/Network error/)).toBeInTheDocument();
    // The combobox input should not be rendered in error state
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
  });

  it('calls onSelect with the product_id when a product is clicked', () => {
    const onSelect = jest.fn();
    render(
      <ProductSelector
        products={PRODUCTS}
        selectedProduct={null}
        onSelect={onSelect}
      />
    );
    fireEvent.focus(screen.getByRole('combobox'));
    fireEvent.click(screen.getByText(/Widget Alpha/));
    expect(onSelect).toHaveBeenCalledWith('P001');
  });
});

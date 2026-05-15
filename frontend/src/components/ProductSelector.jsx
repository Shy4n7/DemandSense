/**
 * ProductSelector — searchable dropdown that filters products by name and ID.
 *
 * Requirements: 8.1, 8.5, 14.5
 */

import { useState, useRef, useEffect } from 'react';
import SkeletonLoader from './SkeletonLoader';

/**
 * @param {object} props
 * @param {Array<{product_id: string, description: string}>} props.products
 * @param {string|null} props.selectedProduct - Currently selected product_id
 * @param {function} props.onSelect - Called with product_id when a product is chosen
 * @param {boolean} props.loading - Whether products are being fetched
 * @param {string|null} props.error - Error message if products failed to load
 */
export default function ProductSelector({
  products = [],
  selectedProduct,
  onSelect,
  loading = false,
  error = null,
}) {
  const [query, setQuery] = useState('');
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(e) {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  if (loading) {
    return (
      <div className="w-full max-w-sm">
        <SkeletonLoader rows={2} />
      </div>
    );
  }

  if (error) {
    return (
      <div className="w-full max-w-sm rounded-lg border border-red-200 bg-red-50 p-3">
        <p className="text-sm text-red-700">
          {error} Please refresh the page to try again.
        </p>
      </div>
    );
  }

  // Filter products by query (case-insensitive match on name or ID)
  const lowerQuery = query.toLowerCase();
  const filtered = products.filter(
    (p) =>
      p.description.toLowerCase().includes(lowerQuery) ||
      p.product_id.toLowerCase().includes(lowerQuery)
  );

  const selectedLabel = selectedProduct
    ? products.find((p) => p.product_id === selectedProduct)
    : null;

  function handleSelect(productId) {
    onSelect(productId);
    setQuery('');
    setIsOpen(false);
  }

  return (
    <div className="relative w-full max-w-sm" ref={containerRef}>
      <label
        htmlFor="product-search"
        className="mb-1 block text-sm font-medium text-gray-700"
      >
        Product
      </label>

      {/* Trigger / search input */}
      <div
        className="flex cursor-pointer items-center rounded-lg border border-gray-300 bg-white px-3 py-2 shadow-sm focus-within:border-blue-500 focus-within:ring-1 focus-within:ring-blue-500"
        onClick={() => setIsOpen(true)}
      >
        <input
          id="product-search"
          type="text"
          className="flex-1 bg-transparent text-sm text-gray-900 placeholder-gray-400 outline-none"
          placeholder={
            selectedLabel
              ? `${selectedLabel.product_id} — ${selectedLabel.description}`
              : 'Search by name or ID…'
          }
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setIsOpen(true);
          }}
          onFocus={() => setIsOpen(true)}
          aria-autocomplete="list"
          aria-controls="product-listbox"
          aria-expanded={isOpen}
          role="combobox"
        />
        {/* Chevron */}
        <svg
          className={`ml-2 h-4 w-4 flex-shrink-0 text-gray-400 transition-transform ${isOpen ? 'rotate-180' : ''}`}
          viewBox="0 0 20 20"
          fill="currentColor"
          aria-hidden="true"
        >
          <path
            fillRule="evenodd"
            d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z"
            clipRule="evenodd"
          />
        </svg>
      </div>

      {/* Dropdown list */}
      {isOpen && (
        <ul
          id="product-listbox"
          role="listbox"
          className="absolute z-10 mt-1 max-h-60 w-full overflow-auto rounded-lg border border-gray-200 bg-white py-1 shadow-lg"
        >
          {filtered.length === 0 ? (
            <li className="px-3 py-2 text-sm text-gray-500">No products found</li>
          ) : (
            filtered.map((p) => (
              <li
                key={p.product_id}
                role="option"
                aria-selected={p.product_id === selectedProduct}
                className={`cursor-pointer px-3 py-2 text-sm hover:bg-blue-50 ${
                  p.product_id === selectedProduct
                    ? 'bg-blue-50 font-medium text-blue-700'
                    : 'text-gray-900'
                }`}
                onClick={() => handleSelect(p.product_id)}
              >
                <span className="font-mono text-xs text-gray-500">{p.product_id}</span>
                {' — '}
                {p.description}
              </li>
            ))
          )}
        </ul>
      )}
    </div>
  );
}

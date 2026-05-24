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
      <div className="w-full">
        <SkeletonLoader rows={2} />
      </div>
    );
  }

  if (error) {
    return (
      <div className="w-full rounded-lg border border-red-500/30 bg-red-950/20 p-3">
        <p className="text-sm text-red-300">
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
    <div className="relative w-full" ref={containerRef}>
      <label
        htmlFor="product-search"
        className="mb-1.5 block text-sm font-semibold text-slate-300"
      >
        Product
      </label>

      {/* Trigger / search input */}
      <div
        className="flex cursor-pointer items-center rounded-lg border border-white/10 bg-slate-900/40 px-3 py-2.5 shadow-sm focus-within:border-indigo-500 focus-within:ring-1 focus-within:ring-indigo-500 transition-all duration-300"
        onClick={() => setIsOpen(true)}
      >
        <input
          id="product-search"
          type="text"
          className="flex-1 bg-transparent text-sm text-slate-100 placeholder-slate-500 outline-none"
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
          className={`ml-2 h-4 w-4 flex-shrink-0 text-slate-400 transition-transform duration-300 ${isOpen ? 'rotate-180' : ''}`}
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
          className="absolute z-10 mt-1.5 max-h-60 w-full overflow-auto rounded-lg glass-card border border-white/10 py-1 shadow-2xl text-slate-200"
        >
          {filtered.length === 0 ? (
            <li className="px-3 py-2 text-sm text-slate-400">No products found</li>
          ) : (
            filtered.map((p) => (
              <li
                key={p.product_id}
                role="option"
                aria-selected={p.product_id === selectedProduct}
                className={`cursor-pointer px-3 py-2 text-sm transition-colors duration-200 ${
                  p.product_id === selectedProduct
                    ? 'bg-indigo-600/20 font-medium text-indigo-300 border-l-2 border-indigo-500'
                    : 'hover:bg-indigo-600/30 hover:text-white text-slate-200'
                }`}
                onClick={() => handleSelect(p.product_id)}
              >
                <span className="font-mono text-xs text-indigo-400 font-semibold">{p.product_id}</span>
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

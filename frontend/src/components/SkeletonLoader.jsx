/**
 * SkeletonLoader — animated placeholder displayed while API responses are pending.
 * Uses Tailwind CSS animate-pulse for the pulsing gray bars effect.
 *
 * Requirements: 14.1, 14.2, 14.3
 */

/**
 * @param {object} props
 * @param {number} [props.rows=3] - Number of skeleton bars to render
 * @param {string} [props.className] - Additional Tailwind classes for the container
 */
export default function SkeletonLoader({ rows = 3, className = '' }) {
  return (
    <div
      className={`animate-pulse space-y-3 ${className}`}
      role="status"
      aria-label="Loading"
    >
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="h-4 bg-gray-200 rounded"
          style={{ width: `${85 - i * 10}%` }}
        />
      ))}
      <span className="sr-only">Loading…</span>
    </div>
  );
}

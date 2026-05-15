/**
 * ErrorMessage — displays an error message with a retry button.
 *
 * Requirements: 14.1, 14.2, 14.3
 */

/**
 * @param {object} props
 * @param {string} props.message - The error message to display
 * @param {function} [props.onRetry] - Callback invoked when the retry button is clicked
 */
export default function ErrorMessage({ message, onRetry }) {
  return (
    <div
      className="flex flex-col items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-4"
      role="alert"
    >
      <div className="flex items-start gap-2">
        {/* Error icon */}
        <svg
          className="mt-0.5 h-5 w-5 flex-shrink-0 text-red-500"
          viewBox="0 0 20 20"
          fill="currentColor"
          aria-hidden="true"
        >
          <path
            fillRule="evenodd"
            d="M10 18a8 8 0 100-16 8 8 0 000 16zm-.75-9.25a.75.75 0 011.5 0v3.5a.75.75 0 01-1.5 0v-3.5zm.75 6a.75.75 0 100-1.5.75.75 0 000 1.5z"
            clipRule="evenodd"
          />
        </svg>
        <p className="text-sm text-red-700">{message}</p>
      </div>

      {onRetry && (
        <button
          onClick={onRetry}
          className="rounded-md bg-red-100 px-3 py-1.5 text-sm font-medium text-red-700 hover:bg-red-200 focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-offset-1 transition-colors"
        >
          Retry
        </button>
      )}
    </div>
  );
}

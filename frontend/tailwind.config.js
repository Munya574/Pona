/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      // Named after what Pona FOUND, not a judgement on the food.
      // The old names (safe/caution/unsafe) rated the food itself.
      colors: {
        clear: '#22c55e',     // no triggers found
        possible: '#f59e0b',  // possible triggers
        present: '#ef4444',   // contains something you listed
      },
    },
  },
  plugins: [],
}

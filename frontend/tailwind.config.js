/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: '#090a0f',
        surface: {
          50: '#1e2230',
          100: '#161924',
          200: '#12141c',
          300: '#0d0f15',
        },
        accent: {
          DEFAULT: '#10b981',
          hover: '#059669',
          light: '#34d399',
          subtle: 'rgba(16, 185, 129, 0.12)',
        },
        border: '#232736',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'Consolas', 'monospace'],
      }
    },
  },
  plugins: [],
}

/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#15181d',
        muted: '#5b6472',
        line: '#e2e6ed',
        panel: '#f6f8fb',
        critical: '#8b1a1a',
        high: '#b3541e',
        medium: '#8a6d1a',
        low: '#2c6e49',
        info: '#39506b',
      },
      fontFamily: {
        serif: ['Iowan Old Style', 'Palatino Linotype', 'Palatino', 'Georgia', 'serif'],
        sans: ['Inter', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
      },
    },
  },
  plugins: [],
}

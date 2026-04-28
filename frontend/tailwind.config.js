/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        primary: { 50: '#eef6ff', 100: '#d9eaff', 200: '#bcdbff', 300: '#8ec5ff', 400: '#59a4ff', 500: '#3381ff', 600: '#1a5ff7', 700: '#154ae3', 800: '#173db8', 900: '#193891', 950: '#142358' },
        surface: { 50: '#f4f4f8', 100: '#e9e9f0', 200: '#d3d3e1', 300: '#b2b2c9', 400: '#8b8bab', 500: '#6d6d90', 600: '#585878', 700: '#484862', 800: '#3e3e53', 900: '#1a1a2e', 950: '#0f0f1a' },
        danger: { 400: '#f87171', 500: '#ef4444', 600: '#dc2626' },
        warning: { 400: '#fbbf24', 500: '#f59e0b', 600: '#d97706' },
        success: { 400: '#4ade80', 500: '#22c55e', 600: '#16a34a' },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'glow': 'glow 2s ease-in-out infinite alternate',
      },
      keyframes: {
        glow: {
          '0%': { boxShadow: '0 0 5px rgba(51,129,255,0.3)' },
          '100%': { boxShadow: '0 0 20px rgba(51,129,255,0.6)' },
        },
      },
    },
  },
  plugins: [],
};

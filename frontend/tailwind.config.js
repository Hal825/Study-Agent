/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Brand palette — "Studio Light"
        ink: {
          DEFAULT: '#1E1B18',
          soft: '#5C5853',
          muted: '#8C8882',
        },
        paper: {
          DEFAULT: '#F7F6F3',
          dark: '#EEECE7',
        },
        surface: '#FFFFFF',
        border: {
          DEFAULT: '#E8E4DE',
          light: '#F0EDE8',
        },
        // Primary — muted steel blue, replacing generic #3b82f6
        primary: {
          50: '#F2F5F8',
          100: '#E4EAF0',
          200: '#C5D2DE',
          300: '#9DB2C6',
          400: '#7A95AE',
          500: '#5C7B98',
          600: '#4A6074',
          700: '#3C4E5E',
          800: '#2E3D4A',
          900: '#202B35',
        },
        // Signature accent — warm gold
        gold: {
          50: '#FCF8F2',
          100: '#F7EFE1',
          200: '#EED7B8',
          300: '#E2BC8A',
          400: '#D4A55E',
          500: '#B8944F',
          600: '#9C7A3E',
          700: '#7D6132',
          800: '#5F4A28',
          900: '#40321D',
        },
      },
      fontFamily: {
        display: ['Georgia', 'Times New Roman', 'serif'],
        body: ['Inter', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['JetBrains Mono', 'SF Mono', 'Consolas', 'monospace'],
      },
      fontSize: {
        '2xs': ['0.6875rem', { lineHeight: '1.2' }],
      },
      spacing: {
        '18': '4.5rem',
      },
      animation: {
        'pulse-dot': 'pulse-dot 1.4s infinite ease-in-out both',
        'fade-in': 'fade-in 0.4s ease-out',
        'slide-up': 'slide-up 0.4s ease-out',
        'slide-in-right': 'slide-in-right 0.3s ease-out',
      },
      keyframes: {
        'pulse-dot': {
          '0%, 80%, 100%': { transform: 'scale(0)', opacity: '0' },
          '40%': { transform: 'scale(1)', opacity: '1' },
        },
        'fade-in': {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        'slide-up': {
          '0%': { opacity: '0', transform: 'translateY(12px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'slide-in-right': {
          '0%': { opacity: '0', transform: 'translateX(16px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
      },
      boxShadow: {
        'card': '0 1px 3px rgba(30, 27, 24, 0.04), 0 1px 2px rgba(30, 27, 24, 0.03)',
        'card-hover': '0 4px 12px rgba(30, 27, 24, 0.06), 0 2px 4px rgba(30, 27, 24, 0.04)',
        'panel': '0 0 0 1px rgba(30, 27, 24, 0.04), 0 2px 8px rgba(30, 27, 24, 0.06)',
      },
    },
  },
  plugins: [],
}

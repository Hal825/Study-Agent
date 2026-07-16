/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // ── "Warm Paper" palette ──
        // 暖色调 + 低对比度，柔和简约
        ink: {
          DEFAULT: '#2D2A26',    // 主文字 — 暖黑，非纯黑
          soft: '#6B6762',       // 次要文字 — 暖灰
          muted: '#9B9792',      // 辅助文字 — 浅暖灰
        },
        paper: {
          DEFAULT: '#FAF9F6',    // 页面底色 — 奶油白
          dark: '#F2F0EC',       // 微偏深的底色
        },
        surface: {
          DEFAULT: '#FFFFFF',    // 卡片/面板底色
        },
        border: {
          DEFAULT: '#EDEAE5',    // 分割线 — 极淡暖灰
          light: '#F3F1ED',      // 更淡的分割
        },
        // 柔和石灰色 — 替代原 steel blue
        primary: {
          50:  '#F5F4F2',
          100: '#EBE8E4',
          200: '#D7D2CC',
          300: '#B8B1A8',
          400: '#9A9186',
          500: '#7D7469',
          600: '#655D54',
          700: '#4F4942',
          800: '#3B3631',
          900: '#292522',
        },
        // 暖琥珀色 — 点缀色，替代原 gold
        accent: {
          50:  '#FDF9F3',
          100: '#F9F0E2',
          200: '#F1DCBC',
          300: '#E6C38D',
          400: '#D8A95E',
          500: '#C8984E',
          600: '#A87B3C',
          700: '#87602E',
          800: '#664724',
          900: '#45301A',
        },
        // 语义色 — 简约但有层次的彩色点缀
        emerald: {
          50:  '#F3FAF7',
          100: '#E6F4EC',
          200: '#C3E5D3',
          300: '#94D1B2',
          400: '#65B88E',
          500: '#3D9F6E',
          600: '#2E8256',
          700: '#246645',
          800: '#1C4F35',
          900: '#153A27',
        },
        sky: {
          50:  '#F4F8FB',
          100: '#E7F0F7',
          200: '#C8DCF0',
          300: '#9CC1E4',
          400: '#6DA0D2',
          500: '#4A82BF',
          600: '#3A699E',
          700: '#2E537D',
          800: '#234060',
          900: '#1A2E45',
        },
        rose: {
          50:  '#FDF6F5',
          100: '#FAEAE7',
          200: '#F4CFC8',
          300: '#EAA89A',
          400: '#DD7B67',
          500: '#C85640',
          600: '#A4412F',
          700: '#823224',
          800: '#63261C',
          900: '#471B14',
        },
        violet: {
          50:  '#F8F6FB',
          100: '#EFEAF6',
          200: '#DBCFED',
          300: '#C0A9DF',
          400: '#A07ECC',
          500: '#8058B5',
          600: '#674394',
          700: '#513475',
          800: '#3D2858',
          900: '#2C1D40',
        },
      },
      fontFamily: {
        display: ['Georgia', 'Times New Roman', 'serif'],
        body: ['Inter', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['JetBrains Mono', 'SF Mono', 'Consolas', 'monospace'],
      },
      fontSize: {
        '2xs': ['0.6875rem', { lineHeight: '1.3' }],
      },
      borderRadius: {
        'xl': '0.75rem',
        '2xl': '1rem',
        '3xl': '1.25rem',
      },
      animation: {
        'fade-in': 'fade-in 0.5s ease-out',
        'slide-up': 'slide-up 0.4s ease-out',
        'slide-in-right': 'slide-in-right 0.3s ease-out',
        'pulse-soft': 'pulse-soft 2s ease-in-out infinite',
      },
      keyframes: {
        'fade-in': {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        'slide-up': {
          '0%': { opacity: '0', transform: 'translateY(16px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'slide-in-right': {
          '0%': { opacity: '0', transform: 'translateX(16px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
        'pulse-soft': {
          '0%, 100%': { opacity: '0.5' },
          '50%': { opacity: '1' },
        },
      },
      boxShadow: {
        'card': '0 1px 2px rgba(45, 42, 38, 0.03), 0 1px 3px rgba(45, 42, 38, 0.02)',
        'card-hover': '0 2px 8px rgba(45, 42, 38, 0.05), 0 1px 3px rgba(45, 42, 38, 0.03)',
        'panel': '0 0 0 1px rgba(45, 42, 38, 0.03), 0 4px 16px rgba(45, 42, 38, 0.05)',
      },
    },
  },
  plugins: [],
}

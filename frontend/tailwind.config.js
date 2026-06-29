/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // 手绘水墨风配色 - 来自 Demo 设计
        lake: {
          DEFAULT: '#174d5e',
          light: '#2f6b78',
          dark: '#0f3a47',
        },
        lamp: {
          DEFAULT: '#ff8a4c',
          light: '#ffa066',
          dark: '#e6743a',
        },
        grass: '#79a86b',
        sun: '#f2c85b',
        // 纸张/墨水系
        ink: {
          DEFAULT: '#152629',
          sub: '#40575b',
          muted: '#71858a',
          disabled: '#a8b4b6',
        },
        paper: '#f8fbfa',
        mist: '#eaf1f3',
        line: '#d4e0e2',
        // 功能色
        danger: '#d95f59',
        warning: '#f2c85b',
        info: '#5d80b2',
        success: '#79a86b',
        // 兼容旧引用
        primary: {
          DEFAULT: '#174d5e',
          light: '#eaf1f3',
        },
        'bg-body': '#eaf1f3',
        'bg-surface': '#f8fbfa',
        'text-main': '#152629',
        'text-sub': '#40575b',
        'text-disabled': '#a8b4b6',
        border: '#d4e0e2',
        error: '#d95f59',
      },
      fontFamily: {
        display: ['"STKaiti"', '"KaiTi"', '"Noto Serif SC"', 'serif'],
        sans: ['"PingFang SC"', '"Microsoft YaHei"', '"Noto Sans SC"', 'sans-serif'],
        data: ['"DIN Alternate"', '"Arial Narrow"', '"Segoe UI"', 'sans-serif'],
        mono: ['"SF Mono"', 'Monaco', '"Cascadia Code"', '"Roboto Mono"', 'Consolas', 'monospace'],
      },
      borderRadius: {
        sm: '10px',
        md: '14px',
        lg: '20px',
        xl: '28px',
        '2xl': '32px',
      },
      boxShadow: {
        sm: '0 8px 24px rgba(20, 55, 63, 0.09)',
        md: '0 12px 32px rgba(20, 55, 63, 0.10)',
        lg: '0 18px 50px rgba(20, 55, 63, 0.11)',
        xl: '0 24px 64px rgba(20, 55, 63, 0.14)',
        lamp: '0 10px 22px rgba(255, 138, 76, 0.24)',
        lake: '0 10px 24px rgba(23, 77, 94, 0.22)',
      },
      animation: {
        'slide-in': 'slideIn 0.3s ease-out',
        'pin-in': 'pinIn 0.45s both',
        'fade-in': 'fadeIn 0.2s ease',
        'modal-in': 'modalIn 0.25s ease',
        'pulse-soft': 'pulseSoft 2s infinite',
      },
      keyframes: {
        slideIn: {
          '0%': { transform: 'translateX(100%)', opacity: '0' },
          '100%': { transform: 'translateX(0)', opacity: '1' },
        },
        pinIn: {
          'from': { opacity: '0', transform: 'translate(-50%,-84%) scale(.82)' },
          'to': { opacity: '1', transform: 'translate(-50%,-100%) scale(1)' },
        },
        fadeIn: {
          'from': { opacity: '0' },
          'to': { opacity: '1' },
        },
        modalIn: {
          'from': { opacity: '0', transform: 'translateY(16px) scale(.98)' },
          'to': { opacity: '1', transform: 'none' },
        },
        pulseSoft: {
          '50%': { boxShadow: '0 0 0 9px rgba(121,168,107,0)' },
        },
      },
    },
  },
  plugins: [],
}

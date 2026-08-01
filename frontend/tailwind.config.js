/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        lake: {
          DEFAULT: '#174d5e',
          light: '#2d6270',
          dark: '#0f3a47',
        },
        lamp: {
          DEFAULT: '#a9471d',
          light: '#f08a5a',
          dark: '#8f3815',
        },
        grass: '#47754e',
        sun: '#765c12',
        ink: {
          DEFAULT: '#152629',
          sub: '#3d5458',
          muted: '#566a6e',
          disabled: '#9aabae',
          divider: '#e8eded',
        },
        paper: '#fafcfb',
        mist: '#f4f7f6',
        'paper-alt': '#f6f3ed',
        'paper-hover': '#edf1f2',
        line: {
          DEFAULT: '#d8e1e3',
          strong: '#c4d0d3',
        },
        danger: '#a33e39',
        warning: '#765c12',
        info: '#5878a6',
        success: '#47754e',
        primary: {
          DEFAULT: '#174d5e',
          light: '#e7f0f1',
        },
        'bg-body': '#f4f7f6',
        'bg-surface': '#fafcfb',
        'text-main': '#152629',
        'text-sub': '#3d5458',
        'text-disabled': '#9aabae',
        border: '#d8e1e3',
        error: '#a33e39',
      },
      fontFamily: {
        display: ['"STKaiti"', '"KaiTi"', '"Noto Serif SC"', 'serif'],
        sans: ['"PingFang SC"', '"Microsoft YaHei"', '"Noto Sans SC"', 'sans-serif'],
        data: ['"DIN Alternate"', '"Arial Narrow"', '"Segoe UI"', 'sans-serif'],
        mono: ['"SF Mono"', 'Monaco', '"Cascadia Code"', '"Roboto Mono"', 'Consolas', 'monospace'],
      },
      borderRadius: {
        sm: '6px',
        md: '10px',
        lg: '16px',
        xl: '20px',
      },
      boxShadow: {
        sm: '0 2px 8px rgba(21, 38, 41, 0.06)',
        DEFAULT: '0 4px 16px rgba(21, 38, 41, 0.06), 0 1px 3px rgba(21, 38, 41, 0.04)',
        md: '0 4px 16px rgba(21, 38, 41, 0.06), 0 1px 3px rgba(21, 38, 41, 0.04)',
        lg: '0 8px 28px rgba(21, 38, 41, 0.10), 0 2px 6px rgba(21, 38, 41, 0.05)',
        xl: '0 12px 40px rgba(21, 38, 41, 0.08)',
        modal: '0 16px 48px rgba(21, 38, 41, 0.14)',
        lamp: '0 6px 16px rgba(230, 115, 64, 0.22)',
        lake: '0 6px 18px rgba(23, 77, 94, 0.18)',
      },
      animation: {
        'slide-in': 'slideIn 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
        'pin-in': 'pinIn 0.45s cubic-bezier(0.16, 1, 0.3, 1) both',
        'fade-in': 'fadeIn 0.25s cubic-bezier(0.16, 1, 0.3, 1)',
        'modal-in': 'modalIn 0.28s cubic-bezier(0.16, 1, 0.3, 1)',
        'stagger-in': 'staggerIn 0.35s cubic-bezier(0.16, 1, 0.3, 1) both',
      },
      keyframes: {
        slideIn: {
          '0%': { transform: 'translateX(100%)', opacity: '0' },
          '100%': { transform: 'translateX(0)', opacity: '1' },
        },
        pinIn: {
          'from': { opacity: '0', transform: 'translate(-50%,-84%) scale(.88)' },
          'to': { opacity: '1', transform: 'translate(-50%,-100%) scale(1)' },
        },
        fadeIn: {
          'from': { opacity: '0' },
          'to': { opacity: '1' },
        },
        modalIn: {
          'from': { opacity: '0', transform: 'translateY(12px) scale(.98)' },
          'to': { opacity: '1', transform: 'none' },
        },
        staggerIn: {
          'from': { opacity: '0', transform: 'translateY(10px)' },
          'to': { opacity: '1', transform: 'translateY(0)' },
        },
      },
    },
  },
  plugins: [],
}

/**
 * 设计令牌（Design Tokens）
 * 手绘水墨风 - 基于 Demo 设计规范
 */

// 颜色系统
export const colors = {
  // 墨水系
  ink: '#152629',
  inkSub: '#40575b',
  muted: '#71858a',
  inkDisabled: '#a8b4b6',

  // 纸张/背景
  paper: '#f8fbfa',
  mist: '#eaf1f3',

  // 主色 - 湖水蓝
  lake: '#174d5e',
  lakeLight: '#2f6b78',
  lakeDark: '#0f3a47',

  // 强调色 - 灯笼橙
  lamp: '#ff8a4c',
  lampLight: '#ffa066',
  lampDark: '#e6743a',

  // 辅助色
  grass: '#79a86b',
  sun: '#f2c85b',

  // 线条
  line: '#d4e0e2',

  // 功能色
  danger: '#d95f59',
  warning: '#f2c85b',
  info: '#5d80b2',
  success: '#79a86b',

  // 分类色板
  category: {
    food: { main: '#ef7b5c', light: '#fdf2e9' },
    event: { main: '#8f72bd', light: '#f5eef8' },
    service: { main: '#4d8791', light: '#eaf3f4' },
    study: { main: '#5d80b2', light: '#eef3fa' },
    lostFound: { main: '#de9e39', light: '#fbf3e3' },
    club: { main: '#68a56f', light: '#edf5ef' },
    default: { main: '#71858a', light: '#edf3f4' },
  },
} as const;

// 字体系统
export const fonts = {
  family: {
    display: '"STKaiti", "KaiTi", "Noto Serif SC", serif',
    sans: '"PingFang SC", "Microsoft YaHei", "Noto Sans SC", sans-serif',
    data: '"DIN Alternate", "Arial Narrow", "Segoe UI", sans-serif',
    mono: '"SF Mono", Monaco, "Cascadia Code", "Roboto Mono", Consolas, "Courier New", monospace',
  },

  heading: {
    h1: { mobile: '24px', desktop: '30px', lineHeight: 1.2, fontWeight: 800 },
    h2: { mobile: '20px', desktop: '24px', lineHeight: 1.25, fontWeight: 800 },
    h3: { mobile: '18px', desktop: '20px', lineHeight: 1.35, fontWeight: 700 },
    h4: { mobile: '16px', desktop: '18px', lineHeight: 1.4, fontWeight: 700 },
    h5: { mobile: '14px', desktop: '16px', lineHeight: 1.5, fontWeight: 700 },
    h6: { mobile: '12px', desktop: '14px', lineHeight: 1.5, fontWeight: 700 },
  },

  body: {
    large: { size: '16px', lineHeight: 1.65, fontWeight: 400 },
    normal: { size: '14px', lineHeight: 1.65, fontWeight: 400 },
    small: { size: '12px', lineHeight: 1.55, fontWeight: 400 },
    xsmall: { size: '10px', lineHeight: 1.4, fontWeight: 400 },
  },
} as const;

// 间距系统
export const spacing = {
  xs: '4px',
  sm: '8px',
  md: '12px',
  lg: '16px',
  xl: '24px',
  '2xl': '32px',
  '3xl': '48px',
} as const;

// 圆角系统 - 手绘风大圆角
export const borderRadius = {
  sm: '10px',
  md: '14px',
  lg: '20px',
  xl: '28px',
  '2xl': '32px',
  full: '9999px',
} as const;

// 阴影系统 - 柔和墨色阴影
export const shadows = {
  sm: '0 8px 24px rgba(20, 55, 63, 0.09)',
  md: '0 12px 32px rgba(20, 55, 63, 0.10)',
  lg: '0 18px 50px rgba(20, 55, 63, 0.11)',
  xl: '0 24px 64px rgba(20, 55, 63, 0.14)',
  lamp: '0 10px 22px rgba(255, 138, 76, 0.24)',
  lake: '0 10px 24px rgba(23, 77, 94, 0.22)',
} as const;

// 图标尺寸
export const iconSize = {
  xs: '12px',
  sm: '16px',
  md: '20px',
  lg: '24px',
  xl: '32px',
  '2xl': '48px',
} as const;

// 按钮尺寸
export const buttonSize = {
  sm: { height: '36px', padding: '8px 14px', fontSize: '13px', iconSize: '14px', radius: '13px' },
  md: { height: '44px', padding: '12px 17px', fontSize: '14px', iconSize: '16px', radius: '14px' },
  lg: { height: '52px', padding: '16px 22px', fontSize: '16px', iconSize: '20px', radius: '16px' },
} as const;

// 输入框尺寸
export const inputSize = {
  md: { height: '44px', padding: '12px 13px', fontSize: '14px', radius: '13px' },
  lg: { height: '52px', padding: '14px 16px', fontSize: '15px', radius: '14px' },
} as const;

// 断点
export const breakpoints = {
  mobile: '320px',
  tablet: '768px',
  desktop: '1024px',
  wide: '1280px',
} as const;

// 过渡动画
export const transitions = {
  fast: '150ms ease',
  normal: '220ms ease',
  slow: '300ms ease',
} as const;

// Z-index 层级
export const zIndex = {
  base: 0,
  content: 1,
  dropdown: 1000,
  sticky: 1020,
  fixed: 1030,
  sidebar: 40,
  modalBackdrop: 100,
  modal: 1050,
  popover: 1060,
  tooltip: 1070,
  toast: 160,
} as const;

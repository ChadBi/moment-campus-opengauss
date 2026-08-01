/**
 * 设计令牌（Design Tokens）
 * 手绘水墨风 - 宣纸质感、墨色层次、克制雅致
 */

// 颜色系统 - 水墨宣纸色系
export const colors = {
  // 五级墨
  ink: '#152629',
  inkSub: '#3d5458',
  muted: '#566a6e',
  inkDisabled: '#9aabae',
  inkDivider: '#e8eded',

  // 宣纸/背景
  paper: '#fafcfb',
  mist: '#f4f7f6',
  paperAlt: '#f6f3ed',
  paperHover: '#edf1f2',

  // 主色 - 墨青/湖水蓝
  lake: '#174d5e',
  lakeLight: '#2d6270',
  lakeDark: '#0f3a47',

  // 强调色 - 朱砂/灯笼橙
  lamp: '#a9471d',
  lampLight: '#f08a5a',
  lampDark: '#8f3815',

  // 辅助色（略降饱和度，与水墨协调）
  grass: '#47754e',
  sun: '#765c12',

  // 线条 - 墨线层次
  line: '#d8e1e3',
  lineStrong: '#c4d0d3',

  // 功能色
  danger: '#a33e39',
  warning: '#765c12',
  info: '#5878a6',
  success: '#47754e',

  // 分类色板
  category: {
    food: { main: '#e07454', light: '#f9ede7' },
    event: { main: '#866cb0', light: '#f2ebf6' },
    service: { main: '#497d86', light: '#e7f0f1' },
    study: { main: '#5878a6', light: '#ebf0f7' },
    lostFound: { main: '#cf9335', light: '#f8efe0' },
    club: { main: '#639b69', light: '#ebf2ed' },
    default: { main: '#6a7d81', light: '#edf1f2' },
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
    h2: { mobile: '20px', desktop: '26px', lineHeight: 1.3, fontWeight: 800 },
    h3: { mobile: '18px', desktop: '20px', lineHeight: 1.4, fontWeight: 700 },
    h4: { mobile: '16px', desktop: '18px', lineHeight: 1.5, fontWeight: 700 },
    h5: { mobile: '14px', desktop: '16px', lineHeight: 1.5, fontWeight: 600 },
    h6: { mobile: '12px', desktop: '14px', lineHeight: 1.5, fontWeight: 600 },
  },

  body: {
    large: { size: '16px', lineHeight: 1.7, fontWeight: 400 },
    normal: { size: '15px', lineHeight: 1.75, fontWeight: 400 },
    small: { size: '13px', lineHeight: 1.6, fontWeight: 400 },
    xsmall: { size: '12px', lineHeight: 1.5, fontWeight: 500 },
  },
} as const;

// 间距系统 - 卷轴呼吸感
export const spacing = {
  xs: '4px',
  sm: '8px',
  md: '12px',
  lg: '16px',
  xl: '20px',
  '2xl': '28px',
  '3xl': '40px',
} as const;

// 圆角系统 - 有层次的"软"
export const borderRadius = {
  none: '0px',
  sm: '6px',
  md: '10px',
  lg: '16px',
  xl: '20px',
  full: '9999px',
} as const;

// 阴影系统 - 墨韵晕染
export const shadows = {
  sm: '0 2px 8px rgba(21, 38, 41, 0.06)',
  md: '0 4px 16px rgba(21, 38, 41, 0.06), 0 1px 3px rgba(21, 38, 41, 0.04)',
  lg: '0 8px 28px rgba(21, 38, 41, 0.10), 0 2px 6px rgba(21, 38, 41, 0.05)',
  xl: '0 12px 40px rgba(21, 38, 41, 0.08)',
  modal: '0 16px 48px rgba(21, 38, 41, 0.14)',
  lamp: '0 6px 16px rgba(230, 115, 64, 0.22)',
  lake: '0 6px 18px rgba(23, 77, 94, 0.18)',
} as const;

// 图标尺寸
export const iconSize = {
  xs: '12px',
  sm: '14px',
  md: '16px',
  lg: '20px',
  xl: '24px',
  '2xl': '32px',
} as const;

// 按钮尺寸
export const buttonSize = {
  sm: { height: '36px', padding: '8px 14px', fontSize: '13px', iconSize: '14px', radius: '10px' },
  md: { height: '40px', padding: '10px 18px', fontSize: '14px', iconSize: '16px', radius: '10px' },
  lg: { height: '48px', padding: '14px 24px', fontSize: '16px', iconSize: '18px', radius: '10px' },
} as const;

// 输入框尺寸
export const inputSize = {
  md: { height: '40px', padding: '10px 14px', fontSize: '14px', radius: '10px' },
  lg: { height: '48px', padding: '12px 16px', fontSize: '15px', radius: '10px' },
} as const;

// 断点
export const breakpoints = {
  mobile: '320px',
  tablet: '768px',
  desktop: '1024px',
  wide: '1280px',
} as const;

// 过渡动画 - 水墨晕开般柔和
export const transitions = {
  fast: '150ms cubic-bezier(0.16, 1, 0.3, 1)',
  normal: '220ms cubic-bezier(0.16, 1, 0.3, 1)',
  slow: '320ms cubic-bezier(0.16, 1, 0.3, 1)',
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

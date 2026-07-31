/**
 * skeleton 骨架屏组件
 * shimmer 动画 + 多变体（post-card / list-item / profile-card / stats-grid / block）
 * 对齐 skill Section 4.5 "Loading: Skeletal loaders matching the final layout's shape"
 *
 * 用法：
 *   <skeleton variant="post-card" />
 *   <skeleton variant="stats-grid" />
 *   <skeleton variant="block" height="400rpx" />
 */
Component({
  properties: {
    /** 骨架变体：post-card | list-item | profile-card | stats-grid | block */
    variant: {
      type: String,
      value: 'block',
    },
    /** block 变体的高度（仅 variant=block 生效） */
    height: {
      type: String,
      value: '200rpx',
    },
  },
});

/**
 * empty-state 空状态组件
 * 替代 ○ 几何符号凑合的空状态，提供 icon + title + hint + 可选 CTA
 *
 * 用法：
 *   <empty-state
 *     icon="file-text"
 *     title="暂无发布"
 *     hint="发布第一条校园经验"
 *     action-text="去发布"
 *     bind:action="onGoPublish" />
 *
 *   <empty-state compact icon="bell" title="暂无通知" />
 */
Component({
  properties: {
    /** icon 组件 name（默认 sparkles） */
    icon: {
      type: String,
      value: 'sparkles',
    },
    /** 图标颜色（默认 ink-disabled） */
    color: {
      type: String,
      value: '',
    },
    /** 主标题 */
    title: {
      type: String,
      value: '暂无内容',
    },
    /** 副标题（可选） */
    hint: {
      type: String,
      value: '',
    },
    /** CTA 按钮文案（可选） */
    actionText: {
      type: String,
      value: '',
    },
    /** 紧凑模式（列表项空状态） */
    compact: {
      type: Boolean,
      value: false,
    },
  },
  methods: {
    onAction() {
      this.triggerEvent('action');
    },
  },
});

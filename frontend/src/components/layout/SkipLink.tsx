import React from 'react';

/**
 * UX-01.7: 无障碍跳转到主内容链接
 *
 * WCAG 2.2 AA 要求（Success Criterion 2.4.1 Bypass Blocks）：
 *   - 提供跳过重复导航块、直达主内容的机制
 *   - 默认视觉隐藏，键盘 Tab 聚焦时显示
 *
 * 用法：在页面顶部渲染 <SkipLink />，main 元素需有 id="main-content"
 */
export const SkipLink: React.FC<{ targetId?: string }> = ({
  targetId = 'main-content',
}) => {
  return (
    <a
      href={`#${targetId}`}
      className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-[200] focus:px-4 focus:py-2 focus:bg-lake focus:text-white focus:rounded-[8px] focus:shadow-lamp focus:outline-none focus:outline-2 focus:outline-white"
    >
      跳转到主内容
    </a>
  );
};

export default SkipLink;

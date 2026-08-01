import React from 'react';
import { RefreshCw, X } from 'lucide-react';
import { useServiceWorker } from '../hooks/useServiceWorker';

/**
 * UX-01.6: 新版本刷新提示组件
 *
 * 当 Service Worker 检测到新版本时，在右下角显示提示横幅：
 *   - 用户点击"刷新"：调用 skipWaiting + reload
 *   - 用户点击关闭：本次会话不再提示（直到下次 controllerchange）
 *
 * 设计要点：
 *   - 不阻塞用户操作（可关闭）
 *   - 醒目但不过分打扰（右下角浮层）
 *   - 适配 reduce-motion（无动画）
 *   - 移动端友好（响应式宽度）
 */
export const UpdatePrompt: React.FC = () => {
  const { needRefresh, updateServiceWorker } = useServiceWorker();

  if (!needRefresh) return null;

  return <DismissibleUpdatePrompt updateServiceWorker={updateServiceWorker} />;
};

const DismissibleUpdatePrompt: React.FC<{
  updateServiceWorker: () => Promise<void>;
}> = ({ updateServiceWorker }) => {
  const [dismissed, setDismissed] = React.useState(false);

  if (dismissed) return null;

  return (
    <div
      role="alertdialog"
      aria-labelledby="update-title"
      aria-describedby="update-desc"
      className="fixed bottom-4 right-4 left-4 sm:left-auto z-[90] max-w-[400px] sm:w-[360px] bg-ink text-paper rounded-[14px] shadow-lamp border border-white/10 overflow-hidden route-fade-enter"
    >
      <div className="p-4">
        <div className="flex items-start gap-3">
          <div className="w-9 h-9 rounded-[10px] bg-white/10 grid place-items-center flex-shrink-0">
            <RefreshCw size={18} className="text-paper" />
          </div>
          <div className="flex-1 min-w-0">
            <h3 id="update-title" className="text-sm font-semibold text-paper">
              发现新版本
            </h3>
            <p id="update-desc" className="text-xs text-paper/75 mt-0.5">
              此刻校园已更新到新版本，刷新以获取最新体验。
            </p>
          </div>
          <button
            type="button"
            onClick={() => setDismissed(true)}
            className="p-1 rounded text-paper/60 hover:text-paper hover:bg-white/10 transition-colors flex-shrink-0"
            aria-label="关闭提示"
          >
            <X size={16} />
          </button>
        </div>
        <div className="mt-3 flex gap-2">
          <button
            type="button"
            onClick={() => void updateServiceWorker()}
            className="flex-1 h-9 rounded-[8px] bg-lamp text-white text-sm font-medium hover:bg-lamp-dark transition-colors inline-flex items-center justify-center gap-1.5"
          >
            <RefreshCw size={14} />
            立即刷新
          </button>
          <button
            type="button"
            onClick={() => setDismissed(true)}
            className="h-9 px-4 rounded-[8px] bg-white/10 text-paper/85 text-sm hover:bg-white/20 transition-colors"
          >
            稍后
          </button>
        </div>
      </div>
    </div>
  );
};

export default UpdatePrompt;

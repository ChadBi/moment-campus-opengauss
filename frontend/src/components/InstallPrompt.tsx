import React, { useEffect, useState } from 'react';
import { Download, X } from 'lucide-react';

/**
 * UX-01.6: PWA 安装提示
 *
 * 监听浏览器的 beforeinstallprompt 事件，在右下角显示"安装到桌面"提示。
 *   - 用户点击"安装"：触发浏览器原生安装弹窗
 *   - 用户点击关闭：localStorage 记忆本次会话不再提示（避免重复打扰）
 *   - 已安装（beforeinstallprompt 不再触发）：自动隐藏
 *
 * 仅在满足 PWA 安装条件时浏览器才会触发 beforeinstallprompt：
 *   - 已注册 Service Worker
 *   - 已配置 Web App Manifest
 *   - HTTPS 或 localhost
 *   - 用户有足够的互动
 */
interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>;
}

const DISMISS_KEY = 'pwa_install_dismissed';

export const InstallPrompt: React.FC = () => {
  const [deferredPrompt, setDeferredPrompt] = useState<BeforeInstallPromptEvent | null>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    // 已被用户主动关闭过：本次会话不再提示
    if (sessionStorage.getItem(DISMISS_KEY) === '1') return;

    // 已安装（standalone 模式）：不再显示
    if (window.matchMedia('(display-mode: standalone)').matches) return;

    const handler = (e: Event) => {
      // 阻止浏览器默认安装提示（用自定义 UI 替代）
      e.preventDefault();
      setDeferredPrompt(e as BeforeInstallPromptEvent);
      setVisible(true);
    };

    window.addEventListener('beforeinstallprompt', handler);

    // 安装完成后隐藏
    const installedHandler = () => {
      setVisible(false);
      setDeferredPrompt(null);
    };
    window.addEventListener('appinstalled', installedHandler);

    return () => {
      window.removeEventListener('beforeinstallprompt', handler);
      window.removeEventListener('appinstalled', installedHandler);
    };
  }, []);

  const handleInstall = async () => {
    if (!deferredPrompt) return;
    await deferredPrompt.prompt();
    const choice = await deferredPrompt.userChoice;
    if (choice.outcome === 'dismissed') {
      // 用户拒绝：本次会话不再提示
      sessionStorage.setItem(DISMISS_KEY, '1');
    }
    setDeferredPrompt(null);
    setVisible(false);
  };

  const handleDismiss = () => {
    sessionStorage.setItem(DISMISS_KEY, '1');
    setVisible(false);
  };

  if (!visible || !deferredPrompt) return null;

  return (
    <div
      role="dialog"
      aria-labelledby="install-title"
      aria-describedby="install-desc"
      className="fixed bottom-4 right-4 left-4 sm:left-auto z-[85] max-w-[400px] sm:w-[360px] bg-paper text-ink rounded-[14px] shadow-lamp border border-line/60 overflow-hidden route-fade-enter"
    >
      <div className="p-4">
        <div className="flex items-start gap-3">
          <div className="w-9 h-9 rounded-[10px] bg-lake/10 grid place-items-center flex-shrink-0">
            <Download size={18} className="text-lake" />
          </div>
          <div className="flex-1 min-w-0">
            <h3 id="install-title" className="text-sm font-semibold text-ink">
              安装到桌面
            </h3>
            <p id="install-desc" className="text-xs text-ink-muted mt-0.5">
              把"此刻校园"添加到桌面，像 App 一样快速打开。
            </p>
          </div>
          <button
            type="button"
            onClick={handleDismiss}
            className="p-1 rounded text-ink-muted hover:text-ink hover:bg-paper-hover transition-colors flex-shrink-0"
            aria-label="关闭安装提示"
          >
            <X size={16} />
          </button>
        </div>
        <div className="mt-3 flex gap-2">
          <button
            type="button"
            onClick={() => void handleInstall()}
            className="flex-1 h-9 rounded-[8px] bg-lake text-white text-sm font-medium hover:bg-lake-dark transition-colors inline-flex items-center justify-center gap-1.5"
          >
            <Download size={14} />
            安装
          </button>
          <button
            type="button"
            onClick={handleDismiss}
            className="h-9 px-4 rounded-[8px] bg-paper-hover text-ink-sub text-sm hover:bg-line/40 transition-colors"
          >
            以后再说
          </button>
        </div>
      </div>
    </div>
  );
};

export default InstallPrompt;

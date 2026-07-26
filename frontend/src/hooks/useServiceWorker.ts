import { useEffect, useState } from 'react';
import { logger } from '../utils/logger';

/**
 * UX-01.6: Service Worker 注册 + 新版本提示
 *
 * - 仅在生产环境注册（dev 模式 SW 会缓存热更新资源，影响开发体验）
 * - 监听 controllerchange：新 SW 接管时显示刷新提示
 * - 监听 SW_UPDATED 消息：通知用户有新版本
 * - 用户确认后调用 skipWaiting + reload
 *
 * 配套：public/sw.js（应用壳缓存策略，不缓存 /api/*）
 */
export function useServiceWorker(): {
  needRefresh: boolean;
  updateServiceWorker: () => Promise<void>;
} {
  const [needRefresh, setNeedRefresh] = useState(false);
  const [waitingWorker, setWaitingWorker] = useState<ServiceWorker | null>(null);

  useEffect(() => {
    // 仅生产环境注册 SW（避免 dev 模式缓存热更新资源）
    if (import.meta.env.DEV) return;
    if (!('serviceWorker' in navigator)) return;

    let refreshListener: ((event: MessageEvent) => void) | null = null;

    const register = async () => {
      try {
        const registration = await navigator.serviceWorker.register('/sw.js', {
          scope: '/',
          updateViaCache: 'none',
        });

        // 新 SW 等待中：显示刷新提示
        if (registration.waiting) {
          setWaitingWorker(registration.waiting);
          setNeedRefresh(true);
        }

        // 监听新 SW 安装完成
        registration.addEventListener('updatefound', () => {
          const newWorker = registration.installing;
          if (!newWorker) return;
          newWorker.addEventListener('statechange', () => {
            if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
              // 新版本已安装且等待接管
              setWaitingWorker(newWorker);
              setNeedRefresh(true);
            }
          });
        });

        // 监听 SW 主动 postMessage（SW_UPDATED）
        refreshListener = (event: MessageEvent) => {
          if (event.data && event.data.type === 'SW_UPDATED') {
            setNeedRefresh(true);
          }
        };
        navigator.serviceWorker.addEventListener('message', refreshListener);

        // 定期检查更新（每 60 分钟）
        const interval = window.setInterval(() => {
          registration.update().catch(() => {
            // 静默失败
          });
        }, 60 * 60 * 1000);

        return () => window.clearInterval(interval);
      } catch (e) {
        logger.warn('[SW] 注册失败:', e);
      }
    };

    void register();

    return () => {
      if (refreshListener) {
        navigator.serviceWorker.removeEventListener('message', refreshListener);
      }
    };
  }, []);

  const updateServiceWorker = async () => {
    if (waitingWorker) {
      // 通知等待中的 SW 立即接管
      waitingWorker.postMessage({ type: 'SKIP_WAITING' });
    }
    setNeedRefresh(false);
    // 等 controllerchange 后刷新
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.addEventListener('controllerchange', () => {
        window.location.reload();
      }, { once: true });
    } else {
      window.location.reload();
    }
  };

  return { needRefresh, updateServiceWorker };
}

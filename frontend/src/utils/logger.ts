/**
 * P2-007: 轻量 logger（dev 打印 / prod 静默）
 *
 * 设计原则：
 * - dev 环境（import.meta.env.DEV）保持 console 输出，便于调试
 * - prod 环境（import.meta.env.PROD）静默，避免泄露内部错误细节到用户控制台
 * - 保持 console.error 在 prod 也输出致命错误（避免完全失声），但加统一前缀
 * - 不引入 loglevel / winston 等依赖，零成本解决 48 处 console.* 散落问题
 *
 * 使用方式：
 *   import { logger } from '@/utils/logger';
 *   logger.error('加载失败:', error);
 *   logger.warn('订阅状态查询失败:', err);
 */

type LogArgs = unknown[];

const isDev = import.meta.env.DEV;
const isProd = import.meta.env.PROD;

const PREFIX = '[moment-campus]';

export const logger = {
  /** 错误：dev 全量输出；prod 仅输出非空消息字符串（不带敏感对象），便于线上排错 */
  error: (message: string, ...args: LogArgs): void => {
    if (isDev) {
      // eslint-disable-next-line no-console
      console.error(`${PREFIX} ${message}`, ...args);
    } else if (isProd) {
      // prod 仅输出消息前缀，不附带 error 对象（避免泄露后端响应体/堆栈到用户控制台）
      // eslint-disable-next-line no-console
      console.error(`${PREFIX} ${message}`);
    }
  },

  /** 警告：dev 全量输出；prod 静默 */
  warn: (message: string, ...args: LogArgs): void => {
    if (isDev) {
      // eslint-disable-next-line no-console
      console.warn(`${PREFIX} ${message}`, ...args);
    }
    // prod 静默
  },

  /** 信息：dev 输出；prod 静默 */
  info: (message: string, ...args: LogArgs): void => {
    if (isDev) {
      // eslint-disable-next-line no-console
      console.info(`${PREFIX} ${message}`, ...args);
    }
  },

  /** 调试：仅 dev 输出 */
  debug: (message: string, ...args: LogArgs): void => {
    if (isDev) {
      // eslint-disable-next-line no-console
      console.debug(`${PREFIX} ${message}`, ...args);
    }
  },
};

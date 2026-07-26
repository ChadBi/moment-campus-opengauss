/**
 * P3-003: 日期时间格式化工具
 *
 * 合并 17 处重复的 formatDate / formatDateTime 实现，提供 4 种常用格式：
 * - formatRelativeTime：相对时间（"刚刚 / 5分钟前 / 3小时前 / 2天前"）— 用于帖子/通知列表
 * - formatDate：日期（"2026-07-26"）— 用于表格日期列
 * - formatDateTime：日期时间（"2026-07-26 14:30"）— 用于日志/审核时间
 * - formatShortDateTime：短日期时间（"07-26 14:30"）— 用于分析页紧凑展示
 *
 * 全部接受 string | Date | null | undefined，无效输入返回 '-' 或空串
 */

const pad = (n: number): string => n.toString().padStart(2, '0');

function toDate(input: string | Date | null | undefined): Date | null {
  if (input == null || input === '') return null;
  const d = typeof input === 'string' ? new Date(input) : input;
  if (Number.isNaN(d.getTime())) return null;
  return d;
}

/**
 * 相对时间格式化（"刚刚 / 5分钟前 / 3小时前 / 2天前"）
 * 用于帖子列表、通知列表等需要"距今多久"语义的场景。
 */
export function formatRelativeTime(input: string | Date | null | undefined): string {
  const date = toDate(input);
  if (!date) return '';
  const diff = Date.now() - date.getTime();
  if (diff < 0) return '刚刚'; // 未来时间视为刚刚（避免负数显示）
  if (diff < 60_000) return '刚刚';
  const minutes = Math.floor(diff / 60_000);
  if (minutes < 30) return `${minutes}分钟前`;
  const hours = Math.floor(diff / 3_600_000);
  if (hours < 24) return `${hours}小时前`;
  const days = Math.floor(diff / 86_400_000);
  return `${days}天前`;
}

/**
 * 日期格式化（"2026-07-26"）
 * 用于表格日期列、报告日期等只需日期不需时间的场景。
 */
export function formatDate(input: string | Date | null | undefined): string {
  const date = toDate(input);
  if (!date) return '-';
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

/**
 * 完整日期时间格式化（"2026-07-26 14:30"）
 * 用于日志、审核记录、操作时间等需要精确到分钟的场景。
 */
export function formatDateTime(input: string | Date | null | undefined): string {
  const date = toDate(input);
  if (!date) return '-';
  return `${formatDate(date)} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

/**
 * 短日期时间格式化（"07-26 14:30"）
 * 用于分析仪表板等紧凑展示场景（省略年份）。
 */
export function formatShortDateTime(input: string | Date | null | undefined): string {
  const date = toDate(input);
  if (!date) return '-';
  return `${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

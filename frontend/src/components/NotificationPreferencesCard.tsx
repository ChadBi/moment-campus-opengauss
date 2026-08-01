import React, { useCallback, useEffect, useState } from 'react';
import { Bell, ShieldAlert, RefreshCw, CheckCircle } from 'lucide-react';
import {
  notificationsApi,
  type NotificationPreference,
} from '../services/notifications';
import { Button } from './ui/Button';
import { Loading } from './ui/Loading';
import { logger } from '../utils/logger';

/**
 * UX-01.5: 通知偏好卡片
 *
 * 6 类开关：站内即时 / 订阅 / 互动 / 审核 / 治理 / 系统
 * 安全账号通知（system / audit）不可全关：若将 system/audit/instant 全部关闭，
 * 后端返回 400 拒绝，前端回滚到上次保存值并提示。
 *
 * 通知偏好按 user_id 隔离，不区分学校，跨校通知聚合到该用户的通知中心。
 */

interface PrefRow {
  key: keyof Pick<
    NotificationPreference,
    | 'instant_enabled'
    | 'subscription_enabled'
    | 'interaction_enabled'
    | 'audit_enabled'
    | 'governance_enabled'
    | 'system_enabled'
  >;
  label: string;
  desc: string;
  isSecurity?: boolean;
}

type BooleanPrefKey = PrefRow['key'];

const PREF_ROWS: PrefRow[] = [
  {
    key: 'instant_enabled',
    label: '站内即时通知',
    desc: '评论、点赞、审核结果等即时推送至站内通知中心',
    isSecurity: true,
  },
  {
    key: 'subscription_enabled',
    label: '订阅类',
    desc: '订阅的话题/帖子有更新时通知',
  },
  {
    key: 'interaction_enabled',
    label: '互动类',
    desc: '点赞、评论、回复等互动行为通知',
  },
  {
    key: 'audit_enabled',
    label: '审核类',
    desc: '帖子审核通过 / 驳回及备注（安全账号通知不可全关）',
    isSecurity: true,
  },
  {
    key: 'governance_enabled',
    label: '治理类',
    desc: '协同验证状态变化通知',
  },
  {
    key: 'system_enabled',
    label: '系统类',
    desc: '账号安全、产品公告等（安全账号通知不可全关）',
    isSecurity: true,
  },
];

interface NotificationPreferencesCardProps {
  /** 通知变化时回调（用于未来接入实时推送） */
  onPreferencesChange?: (pref: NotificationPreference) => void;
}

export const NotificationPreferencesCard: React.FC<
  NotificationPreferencesCardProps
> = ({ onPreferencesChange }) => {
  const [preferences, setPreferences] = useState<NotificationPreference | null>(null);
  const [loading, setLoading] = useState(true);
  const [savingKey, setSavingKey] = useState<string | null>(null);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'warning' } | null>(null);

  const loadPreferences = useCallback(async () => {
    setLoading(true);
    try {
      const data = await notificationsApi.getPreferences();
      setPreferences(data);
      onPreferencesChange?.(data);
    } catch (error) {
      logger.error('加载通知偏好失败:', error);
      setToast({ message: '加载通知偏好失败', type: 'error' });
    } finally {
      setLoading(false);
    }
  }, [onPreferencesChange]);

  useEffect(() => {
    void Promise.resolve().then(loadPreferences);
  }, [loadPreferences]);

  // 自动消失 toast
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), 2500);
    return () => clearTimeout(timer);
  }, [toast]);

  /**
   * 切换单个开关：乐观更新 + 失败回滚
   * 安全账号通知（system/audit/instant）不可全关由后端校验，
   * 前端在尝试关闭"最后一个安全通道"时给提示但不阻止提交（让后端权威校验）。
   */
  const handleToggle = async (
    key: BooleanPrefKey,
    nextValue: boolean
  ) => {
    if (!preferences) return;
    const prevValue = preferences[key];
    if (prevValue === nextValue) return;

    // 乐观更新
    const optimistic = { ...preferences, [key]: nextValue };
    setPreferences(optimistic);
    setSavingKey(key);

    try {
      const updated = await notificationsApi.updatePreferences({ [key]: nextValue });
      setPreferences(updated);
      onPreferencesChange?.(updated);
      setToast({ message: '通知偏好已更新', type: 'success' });
    } catch (error: unknown) {
      // 回滚
      setPreferences({ ...preferences, [key]: prevValue });
      const e = error as { response?: { data?: { detail?: string } } };
      const detail = e?.response?.data?.detail;
      setToast({
        message: detail || '更新失败，已恢复原设置',
        type: 'error',
      });
    } finally {
      setSavingKey(null);
    }
  };

  if (loading) {
    return (
      <div className="bg-paper rounded-[16px] border border-line/60 p-5 shadow-sm mb-4">
        <div className="flex items-center gap-2 mb-3">
          <Bell size={18} className="text-lake" />
          <h2 className="font-display font-semibold text-ink">通知偏好</h2>
        </div>
        <div className="py-6">
          <Loading text="加载中..." />
        </div>
      </div>
    );
  }

  if (!preferences) {
    return (
      <div className="bg-paper rounded-[16px] border border-line/60 p-5 shadow-sm mb-4">
        <div className="flex items-center gap-2 mb-3">
          <Bell size={18} className="text-lake" />
          <h2 className="font-display font-semibold text-ink">通知偏好</h2>
        </div>
        <div className="py-6 text-center">
          <p className="text-ink-sub text-sm mb-3">通知偏好加载失败</p>
          <Button variant="secondary" size="sm" onClick={loadPreferences} icon={<RefreshCw size={12} />}>
            重新加载
          </Button>
        </div>
      </div>
    );
  }

  return (
    <section
      className="bg-paper rounded-[16px] border border-line/60 p-5 shadow-sm mb-4"
      aria-labelledby="notif-pref-title"
    >
      <div className="flex items-center justify-between mb-1">
        <h2
          id="notif-pref-title"
          className="font-display font-semibold text-ink flex items-center gap-2"
        >
          <Bell size={18} className="text-lake" />
          通知偏好
        </h2>
        {savingKey && (
          <span className="text-[11px] text-ink-muted flex items-center gap-1">
            <RefreshCw size={11} className="animate-spin" />
            保存中...
          </span>
        )}
      </div>
      <p className="text-[11px] text-ink-muted mb-3">
        通知按账号聚合，不区分学校。安全账号通知（系统/审核/即时）不可全部关闭。
      </p>

      {/* 安全提示横幅 */}
      <div className="mb-3 flex items-start gap-1.5 text-[11px] text-sun bg-sun/8 border border-sun/20 rounded-[8px] px-2.5 py-1.5">
        <ShieldAlert size={12} className="flex-shrink-0 mt-[1px]" />
        <span>
          关闭"站内即时通知 + 系统类 + 审核类"中的全部会被后端拒绝，以保证账号安全通知必达。
        </span>
      </div>

      {/* 6 类开关列表 */}
      <ul className="space-y-1" role="list">
        {PREF_ROWS.map((row) => {
          const checked = preferences[row.key];
          const isSaving = savingKey === row.key;
          const switchId = `pref-${row.key}`;
          return (
            <li
              key={row.key}
              className={`flex items-start gap-3 p-2.5 rounded-[10px] transition-colors ${
                row.isSecurity ? 'bg-paper-hover/40' : 'hover:bg-paper-hover/40'
              }`}
            >
              <div className="flex-1 min-w-0">
                <label
                  htmlFor={switchId}
                  className="flex items-center gap-1.5 text-sm font-medium text-ink cursor-pointer"
                >
                  {row.label}
                  {row.isSecurity && (
                    <span
                      className="inline-flex items-center gap-0.5 text-[10px] text-sun bg-sun/10 px-1 py-0.5 rounded-[4px]"
                      title="安全账号通知：不可全部关闭"
                    >
                      <ShieldAlert size={9} /> 安全
                    </span>
                  )}
                </label>
                <p className="text-[11px] text-ink-muted mt-0.5 leading-relaxed">
                  {row.desc}
                </p>
              </div>
              <Switch
                id={switchId}
                checked={checked}
                disabled={isSaving}
                onChange={(next) => handleToggle(row.key, next)}
                aria-label={`${row.label}：${checked ? '已开启' : '已关闭'}，点击切换`}
              />
            </li>
          );
        })}
      </ul>

      {/* Toast */}
      {toast && (
        <div
          role="status"
          aria-live="polite"
          className={`mt-3 flex items-center gap-1.5 text-xs px-3 py-2 rounded-[8px] border ${
            toast.type === 'success'
              ? 'text-grass bg-grass/5 border-grass/20'
              : toast.type === 'warning'
              ? 'text-sun bg-sun/5 border-sun/20'
              : 'text-danger bg-danger/5 border-danger/20'
          }`}
        >
          {toast.type === 'success' ? (
            <CheckCircle size={13} className="flex-shrink-0" />
          ) : (
            <ShieldAlert size={13} className="flex-shrink-0" />
          )}
          <span className="flex-1">{toast.message}</span>
        </div>
      )}
    </section>
  );
};

/**
 * 可访问的开关组件（基于 checkbox + 自定义样式）
 * - role="switch" 提供 ARIA 语义
 * - 键盘可操作（Space / Enter 切换）
 * - 焦点可见（focus-visible ring）
 * - 44px 触控区域（移动端友好）
 */
interface SwitchProps {
  id: string;
  checked: boolean;
  disabled?: boolean;
  onChange: (next: boolean) => void;
  'aria-label'?: string;
}

const Switch: React.FC<SwitchProps> = ({
  id,
  checked,
  disabled,
  onChange,
  ...rest
}) => {
  return (
    <label
      htmlFor={id}
      className={`relative inline-flex items-center flex-shrink-0 ${
        disabled ? 'opacity-60 cursor-not-allowed' : 'cursor-pointer'
      }`}
    >
      <input
        id={id}
        type="checkbox"
        role="switch"
        className="sr-only peer"
        checked={checked}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
        aria-label={rest['aria-label']}
      />
      <span
        className={`w-11 h-6 rounded-full transition-colors duration-200 peer-focus-visible:ring-2 peer-focus-visible:ring-lake peer-focus-visible:ring-offset-2 peer-focus-visible:ring-offset-paper ${
          checked ? 'bg-grass' : 'bg-ink/20'
        }`}
      />
      <span
        className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow-sm transition-transform duration-200 ${
          checked ? 'translate-x-5' : 'translate-x-0'
        }`}
      />
    </label>
  );
};

export default NotificationPreferencesCard;

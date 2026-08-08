import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Search, School as SchoolIcon, AlertTriangle, Check, ArrowRight } from 'lucide-react';
import { Modal } from './ui/Modal';
import { Button } from './ui/Button';
import { useCampusStore } from '../store/useCampusStore';
import { useAuthStore } from '../store/useAuthStore';
import { useSwitchSchool } from '../hooks/useSchoolSync';
import { schoolsApi } from '../services/schools';
import { useUIStore } from '../store/useUIStore';
import { logger } from '../utils/logger';

interface SwitchSchoolModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSwitched?: () => void;
}

/**
 * C-03: 切换学校浮窗（UC-01 严格一对一）
 *
 * - 搜索框按名称/代码过滤公开学校目录
 * - 选择目标学校后弹出后果提示（注册学校认证保留 / 原校内容匿名化 / 当前学校只读）
 * - 确认后调用 joinSchool（后端按切换语义处理）→ 刷新 memberships → 切换 URL
 * - 切换后回调 onSwitched（供个人中心引导认证）
 */
export const SwitchSchoolModal: React.FC<SwitchSchoolModalProps> = ({
  isOpen,
  onClose,
  onSwitched,
}) => {
  const { schools, currentSchoolId, setMemberships } = useCampusStore();
  const { isAuthenticated } = useAuthStore();
  const switchSchool = useSwitchSchool();
  const showToast = useUIStore((s) => s.showToast);

  const [keyword, setKeyword] = useState('');
  const [pendingSchoolId, setPendingSchoolId] = useState<number | null>(null);
  const [switching, setSwitching] = useState(false);

  // 打开时重置
  useEffect(() => {
    if (isOpen) {
      void Promise.resolve().then(() => {
        setKeyword('');
        setPendingSchoolId(null);
        setSwitching(false);
      });
    }
  }, [isOpen]);

  const filtered = useMemo(() => {
    const kw = keyword.trim().toLowerCase();
    if (!kw) return schools;
    return schools.filter(
      (s) => s.name.toLowerCase().includes(kw) || s.code.toLowerCase().includes(kw),
    );
  }, [schools, keyword]);

  const pendingSchool = pendingSchoolId !== null
    ? schools.find((s) => s.id === pendingSchoolId)
    : null;

  const handleConfirmSwitch = useCallback(async () => {
    if (!pendingSchool || !isAuthenticated) return;
    setSwitching(true);
    try {
      // 后端 join 在"已有 active membership 且不同校"时执行切换语义
      const res = await schoolsApi.joinSchool(pendingSchool.code);
      // 刷新 memberships（切换后仅一条 active）
      const list = await schoolsApi.listMyMemberships();
      setMemberships(list);
      await switchSchool(pendingSchool.code);
      showToast(
        res.switched
          ? `已切换到 ${pendingSchool.name}，当前学校仅支持浏览`
          : `已加入 ${pendingSchool.name}`,
        'success',
      );
      setPendingSchoolId(null);
      onClose();
      onSwitched?.();
    } catch (error) {
      logger.error('切换学校失败:', error);
      showToast('切换失败，请稍后重试', 'error');
    } finally {
      setSwitching(false);
    }
  }, [
    pendingSchool, isAuthenticated, setMemberships, switchSchool,
    showToast, onClose, onSwitched,
  ]);

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="切换学校" size="md">
      {/* 搜索框 */}
      <div className="relative mb-4">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink-muted" />
        <input
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          placeholder="搜索学校名称或代号…"
          className="w-full pl-9 pr-3 py-2.5 bg-paper border border-line rounded-[10px] text-sm text-ink placeholder:text-ink-muted/60 focus:outline-none focus:border-lake"
        />
      </div>

      {/* 学校列表 */}
      <div className="max-h-[260px] overflow-y-auto space-y-1.5 mb-4">
        {filtered.length === 0 ? (
          <p className="text-center text-sm text-ink-muted py-6">未找到匹配的学校</p>
        ) : (
          filtered.map((s) => {
            const isCurrent = s.id === currentSchoolId;
            const selected = pendingSchoolId === s.id;
            return (
              <button
                key={s.id}
                type="button"
                disabled={isCurrent}
                onClick={() => setPendingSchoolId(s.id)}
                className={`w-full text-left p-3 rounded-[10px] border transition-colors flex items-center gap-3 ${
                  isCurrent
                    ? 'border-lake/40 bg-lake/[0.04] cursor-default'
                    : selected
                      ? 'border-lake bg-lake/5'
                      : 'border-line hover:bg-paper-hover'
                }`}
              >
                <div className="w-8 h-8 rounded-[8px] bg-lake/10 grid place-items-center flex-shrink-0">
                  <SchoolIcon size={15} className="text-lake" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-ink truncate">{s.name}</div>
                  <div className="text-[11px] text-ink-muted">{s.code}</div>
                </div>
                {isCurrent && (
                  <span className="text-xs text-lake font-medium flex items-center gap-1">
                    <Check size={12} /> 当前
                  </span>
                )}
                {selected && <ArrowRight size={15} className="text-lake flex-shrink-0" />}
              </button>
            );
          })
        )}
      </div>

      {/* 后果提示 + 确认 */}
      {pendingSchool && (
        <div className="border border-warning/30 bg-warning/5 rounded-[10px] p-3">
          <div className="flex items-start gap-2">
            <AlertTriangle size={16} className="text-warning flex-shrink-0 mt-0.5" />
            <div className="text-xs text-ink-sub leading-relaxed">
              <p className="font-medium text-ink mb-1">
                切换到「{pendingSchool.name}」后：
              </p>
              <ul className="list-disc pl-4 space-y-0.5">
                <li>原注册学校的身份认证仍然保留</li>
                <li>原学校已发布的内容将匿名化显示</li>
                <li>在当前学校仅可浏览，切回注册学校后可继续发布和互动</li>
              </ul>
            </div>
          </div>
          <div className="flex gap-2 mt-3">
            <Button
              variant="primary"
              size="sm"
              loading={switching}
              onClick={handleConfirmSwitch}
              className="flex-1"
            >
              确认切换
            </Button>
            <Button
              variant="secondary"
              size="sm"
              disabled={switching}
              onClick={() => setPendingSchoolId(null)}
            >
              取消
            </Button>
          </div>
        </div>
      )}
    </Modal>
  );
};

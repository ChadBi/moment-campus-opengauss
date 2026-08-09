import React, { useEffect, useRef, useState } from 'react';
import { ChevronDown, School as SchoolIcon, Check, Star } from 'lucide-react';
import { useCampusStore } from '../../store/useCampusStore';
import { useAuthStore } from '../../store/useAuthStore';
import { useSwitchSchool } from '../../hooks/useSchoolSync';
import { schoolsApi } from '../../services/schools';
import { SwitchSchoolModal } from '../SwitchSchoolModal';

/**
 * TEN-03.3: 页头学校切换组件
 *
 * - 显示当前学校名称 + 下拉箭头
 * - 点击展开下拉，列出学校目录
 * - 已加入学校显示勾选标记；默认学校显示星标
 * - 切换通过 useSwitchSchool 写入 URL ?school=code
 * - 切换后由 useSchoolSync 取消进行中请求 + 清除旧缓存
 * - UC-01 严格一对一：普通用户点击未加入学校 → 打开 SwitchSchoolModal
 *   （提示切校后果 + 确认），不再静默 join；super_admin 保留多校 join 能力
 *
 * UX-01.7 无障碍优化：
 * - role="listbox" + role="option" + aria-selected
 * - 键盘支持：ArrowDown/ArrowUp 选项间移动，Enter 选择，Escape 关闭
 * - 打开时焦点移至当前选项，关闭时焦点回到触发按钮
 * - aria-haspopup="listbox" + aria-expanded
 */
export const SchoolSwitcher: React.FC = () => {
  const {
    schools,
    memberships,
    currentSchoolId,
    currentSchoolName,
    loadingSchools,
    setMemberships,
    setSchools,
  } = useCampusStore();
  const { isAuthenticated, user } = useAuthStore();
  const switchSchool = useSwitchSchool();
  const [open, setOpen] = useState(false);
  const [switchModalOpen, setSwitchModalOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  // UX-01.7: 当前聚焦选项索引（-1 表示未聚焦任何选项）
  const [activeIndex, setActiveIndex] = useState(-1);
  const optionRefs = useRef<Array<HTMLButtonElement | null>>([]);

  // 点击外部关闭
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(e.target as Node)
      ) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  useEffect(() => {
    if (open) {
      const idx = schools.findIndex((s) => s.id === currentSchoolId);
      requestAnimationFrame(() => {
        if (idx >= 0 && optionRefs.current[idx]) {
          optionRefs.current[idx]?.focus();
        }
      });
    }
  }, [open, schools, currentSchoolId]);

  const openDropdown = () => {
    // 兜底：如果学校列表为空或只有1所，主动拉取
    if (schools.length < 2) {
      schoolsApi.listSchools().then((list) => setSchools(list)).catch(() => undefined);
    }
    const idx = schools.findIndex((s) => s.id === currentSchoolId);
    setActiveIndex(idx >= 0 ? idx : 0);
    setOpen(true);
  };

  // UX-01.7: 键盘导航
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!open) {
      if (e.key === 'ArrowDown' || e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        openDropdown();
      }
      return;
    }
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setActiveIndex((prev) => {
          const next = Math.min(prev + 1, schools.length - 1);
          requestAnimationFrame(() => optionRefs.current[next]?.focus());
          return next;
        });
        break;
      case 'ArrowUp':
        e.preventDefault();
        setActiveIndex((prev) => {
          const next = Math.max(prev - 1, 0);
          requestAnimationFrame(() => optionRefs.current[next]?.focus());
          return next;
        });
        break;
      case 'Home':
        e.preventDefault();
        setActiveIndex(0);
        requestAnimationFrame(() => optionRefs.current[0]?.focus());
        break;
      case 'End': {
        e.preventDefault();
        const last = schools.length - 1;
        setActiveIndex(last);
        requestAnimationFrame(() => optionRefs.current[last]?.focus());
        break;
      }
      case 'Escape':
        e.preventDefault();
        setOpen(false);
        triggerRef.current?.focus();
        break;
      case 'Tab':
        // Tab 关闭下拉，保持自然焦点顺序
        setOpen(false);
        break;
    }
  };

  const handleSelect = async (code: string) => {
    setOpen(false);
    triggerRef.current?.focus();
    // 已是当前学校 → 跳过
    if (
      currentSchoolId !== null &&
      schools.find((s) => s.code === code)?.id === currentSchoolId
    ) {
      return;
    }
    // 登录用户：判断是否已加入该校
    const joined = memberships.some(
      (m) => m.school.code === code && m.status === 'active',
    );
    if (isAuthenticated) {
      if (!joined) {
        // UC-01：super_admin 保留静默 join；普通用户走切换确认浮窗
        if (user?.role === 'super_admin') {
          try {
            await schoolsApi.joinSchool(code);
            const list = await schoolsApi.listMyMemberships();
            setMemberships(list);
          } catch {
            // 加入失败：仍然切换查看公开内容
          }
          await switchSchool(code);
        } else {
          setSwitchModalOpen(true);
        }
        return;
      }
      // 已加入 → 直接切换
      await switchSchool(code);
    } else {
      // 游客：直接切换查看公开内容
      await switchSchool(code);
    }
  };

  if (!currentSchoolName) {
    return (
      <button
        type="button"
        disabled
        className="h-11 min-w-11 px-3 rounded-[10px] bg-paper border border-line/80 inline-flex items-center gap-1.5 text-ink-muted text-sm opacity-60"
        aria-label="尚未选择学校"
      >
        <SchoolIcon size={14} aria-hidden="true" />
        <span className="hidden md:inline">选择学校</span>
      </button>
    );
  }

  const triggerId = 'school-switcher-trigger';
  const listboxId = 'school-switcher-listbox';

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        ref={triggerRef}
        id={triggerId}
        type="button"
        onClick={() => {
          if (open) {
            setOpen(false);
            setActiveIndex(-1);
          } else {
            openDropdown();
          }
        }}
        onKeyDown={handleKeyDown}
        className="h-11 min-w-11 px-3 rounded-[10px] bg-paper border border-line/80 inline-flex items-center gap-1.5 hover:bg-paper-hover transition-colors max-w-[180px] md:max-w-[240px] focus:outline-none focus-visible:ring-2 focus-visible:ring-lake focus-visible:ring-offset-2"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? listboxId : undefined}
        aria-label={`当前学校：${currentSchoolName}，按回车或下箭头键打开切换菜单`}
      >
        <SchoolIcon size={14} className="text-lake flex-shrink-0" aria-hidden="true" />
        <span className="text-sm font-medium text-ink truncate">
          {currentSchoolName}
        </span>
        <ChevronDown
          size={14}
          className={`text-ink-sub flex-shrink-0 transition-transform ${
            open ? 'rotate-180' : ''
          }`}
          aria-hidden="true"
        />
      </button>

      {open && (
        <div
          id={listboxId}
          role="listbox"
          aria-labelledby={triggerId}
          className="absolute right-0 top-full mt-1 min-w-[240px] max-w-[320px] bg-paper border border-line/80 rounded-[12px] shadow-lg overflow-hidden z-50"
        >
          <div className="px-3 py-2 border-b border-line/40 text-xs text-ink-muted">
            {loadingSchools ? '加载学校列表…' : '切换学校（按方向键选择，回车确认，Esc 关闭）'}
          </div>
          <ul className="max-h-[320px] overflow-y-auto py-1">
            {schools.map((s, idx) => {
              const isCurrent = s.id === currentSchoolId;
              const membership = memberships.find((m) => m.school_id === s.id);
              const isJoined = membership?.status === 'active';
              const isDefault = membership?.is_default === true;
              return (
                <li key={s.id}>
                  <button
                    ref={(el) => { optionRefs.current[idx] = el; }}
                    type="button"
                    role="option"
                    aria-selected={isCurrent}
                    tabIndex={idx === activeIndex ? 0 : -1}
                    onClick={() => handleSelect(s.code)}
                    onKeyDown={handleKeyDown}
                    className={`w-full min-h-11 text-left px-3 py-2 flex items-center gap-2 hover:bg-paper-hover focus:bg-paper-hover focus:outline-none transition-colors ${
                      isCurrent ? 'bg-lake/5' : ''
                    }`}
                  >
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-ink truncate">
                        {s.name}
                      </div>
                      <div className="text-[11px] text-ink-muted flex items-center gap-1.5">
                        <span>{s.code}</span>
                        {isJoined && (
                          <span className="inline-flex items-center gap-0.5 text-grass" aria-label="已加入">
                            <Check size={10} aria-hidden="true" /> 已加入
                          </span>
                        )}
                        {isDefault && (
                          <span className="inline-flex items-center gap-0.5 text-sun" aria-label="默认学校">
                            <Star size={10} aria-hidden="true" /> 默认
                          </span>
                        )}
                      </div>
                    </div>
                    {isCurrent && (
                      <Check size={14} className="text-lake flex-shrink-0" aria-hidden="true" />
                    )}
                  </button>
                </li>
              );
            })}
            {schools.length === 0 && !loadingSchools && (
              <li className="px-3 py-3 text-center text-sm text-ink-muted">
                暂无可选学校
              </li>
            )}
          </ul>
          {isAuthenticated && currentSchoolId !== null && (
            <div className="border-t border-line/40 px-3 py-2 text-[11px] text-ink-muted">
              {user?.role === 'super_admin'
                ? '点击未加入学校将自动申请加入'
                : '注册学校可进行校园身份认证，其他学校仅支持浏览'}
            </div>
          )}
        </div>
      )}

      {/* UC-01: 普通用户切换学校确认浮窗 */}
      <SwitchSchoolModal
        isOpen={switchModalOpen}
        onClose={() => setSwitchModalOpen(false)}
      />
    </div>
  );
};

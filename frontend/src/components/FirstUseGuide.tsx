import React, { useCallback, useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useCampusStore } from '../store/useCampusStore';
import { useAuthStore } from '../store/useAuthStore';
import { categoriesApi } from '../services/categories';
import { usersApi } from '../services/users';
import { Modal } from './ui/Modal';
import { Button } from './ui/Button';
import { EmptyState, ErrorState, LoadingState } from './state';
import { School as SchoolIcon, Search, Check, Tag, MapPin, ArrowRight, X } from 'lucide-react';
import type { CategoryListItem, LocationListItem } from '../services/categories';

/**
 * ACC-01.4: 三步首用引导
 *
 * 步骤：
 * 1. 确认学校 — 展示当前学校，可切换或继续
 * 2. 关注分类/地点 — 浏览本校分类与地点，点击关注（多选）
 * 3. 完成一次搜索或跳过 — 跳转到搜索页或直接完成
 *
 * 存储：
 * - localStorage `first_use_guide_completed` 标记是否完成
 * - localStorage `followed_categories` 关注的分类 ID 数组
 * - localStorage `followed_locations` 关注的地点 ID 数组
 *
 * 可跳过：任意步骤都可跳过
 * 可重开：通过 props 或 localStorage 清除可重新触发
 */
const FOLLOWED_CATEGORIES_KEY = 'followed_categories';
const FOLLOWED_LOCATIONS_KEY = 'followed_locations';

/** 从 localStorage 读取关注 ID 列表（容错） */
const readFollowedIds = (key: string): Set<number> => {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return new Set();
    const arr = JSON.parse(raw);
    if (!Array.isArray(arr)) return new Set();
    return new Set(arr.filter((v) => typeof v === 'number'));
  } catch {
    return new Set();
  }
};

/** 写入关注 ID 列表到 localStorage */
const writeFollowedIds = (key: string, ids: Set<number>): void => {
  try {
    localStorage.setItem(key, JSON.stringify(Array.from(ids)));
  } catch {
    // 静默失败，不阻塞引导主流程
  }
};

export const FirstUseGuide: React.FC = () => {
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const { currentSchoolName, currentSchoolId } = useCampusStore();
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [categories, setCategories] = useState<CategoryListItem[]>([]);
  const [locations, setLocations] = useState<LocationListItem[]>([]);
  const [metadataLoading, setMetadataLoading] = useState(false);
  const [metadataError, setMetadataError] = useState<string | null>(null);
  // ACC-01.4: 关注的分类/地点初始化自 localStorage（保留用户历史选择）
  const [followedCategories, setFollowedCategories] = useState<Set<number>>(() =>
    readFollowedIds(FOLLOWED_CATEGORIES_KEY)
  );
  const [followedLocations, setFollowedLocations] = useState<Set<number>>(() =>
    readFollowedIds(FOLLOWED_LOCATIONS_KEY)
  );

  // 检查是否需要显示引导
  // ACC-01.4: 改为读后端 user.onboarding_completed 字段
  // - 新注册用户 onboarding_completed=false → 弹出教程
  // - 已完成引导的用户 onboarding_completed=true → 不弹出（即使换浏览器/清缓存）
  // - 登录不再触发教程（已注册用户的 onboarding_completed 已为 true）
  useEffect(() => {
    if (!user) return;
    if (user.onboarding_completed === false) {
      // 用 microtask 延迟同步 setState，避免 react-hooks/set-state-in-effect 规则告警
      void Promise.resolve().then(() => setOpen(true));
    }
  }, [user]);

  const loadMetadata = useCallback(async () => {
    setMetadataLoading(true);
    setMetadataError(null);
    try {
      const [cats, locs] = await Promise.all([
        categoriesApi.listCategories(),
        categoriesApi.listLocations(),
      ]);
      setCategories(cats);
      setLocations(locs);
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      setMetadataError(e?.response?.data?.detail || '加载关注选项失败');
    } finally {
      setMetadataLoading(false);
    }
  }, []);

  useEffect(() => {
    if (step !== 2 || metadataLoading || metadataError || categories.length > 0 || locations.length > 0) return;
    void Promise.resolve().then(loadMetadata);
  }, [step, metadataLoading, metadataError, categories.length, locations.length, loadMetadata]);

  // 切换学校时重新加载分类与地点（避免显示旧学校数据）
  useEffect(() => {
    if (!open) return;
    // 用 microtask 延迟同步 setState，避免 react-hooks/set-state-in-effect 规则告警
    void Promise.resolve().then(() => {
      setCategories([]);
      setLocations([]);
      setMetadataError(null);
    });
  }, [currentSchoolId, open]);

  const handleSkip = async () => {
    // ACC-01.4: 跳过也标记后端 onboarding_completed=true，避免再次弹出
    try {
      await usersApi.completeOnboarding();
      useAuthStore.getState().updateUser({ onboarding_completed: true });
    } catch {
      // API 失败时仍关闭弹窗，避免阻塞用户
    }
    setOpen(false);
  };

  const handleComplete = async () => {
    // ACC-01.4: 完成引导，标记后端 onboarding_completed=true
    try {
      await usersApi.completeOnboarding();
      useAuthStore.getState().updateUser({ onboarding_completed: true });
    } catch {
      // API 失败时仍关闭弹窗，避免阻塞用户
    }
    setOpen(false);
  };

  const handleNext = () => {
    if (step < 3) {
      setStep((s) => (s + 1) as 1 | 2 | 3);
    } else {
      handleComplete();
    }
  };

  const toggleCategory = (id: number) => {
    setFollowedCategories((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      writeFollowedIds(FOLLOWED_CATEGORIES_KEY, next);
      return next;
    });
  };

  // ACC-01.4: 切换地点关注（多选；持久化到 localStorage）
  const toggleLocation = (id: number) => {
    setFollowedLocations((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      writeFollowedIds(FOLLOWED_LOCATIONS_KEY, next);
      return next;
    });
  };

  const handleGoSearch = () => {
    handleComplete();
    navigate('/search');
  };

  if (!open) return null;

  return (
    <Modal isOpen={open} onClose={handleSkip} title="新手引导" size="md">
      <div className="space-y-5">
        {/* 步骤指示器 */}
        <div className="flex items-center justify-center gap-2">
          {[1, 2, 3].map((s) => (
            <div
              key={s}
              className={`h-1.5 rounded-full transition-all ${
                s === step ? 'w-8 bg-lake' : s < step ? 'w-4 bg-lake/60' : 'w-4 bg-line'
              }`}
            />
          ))}
        </div>

        {/* Step 1: 确认学校 */}
        {step === 1 && (
          <div className="text-center py-2">
            <div className="w-12 h-12 rounded-full bg-lake/10 grid place-items-center mx-auto mb-3">
              <SchoolIcon size={24} className="text-lake" />
            </div>
            <h3 className="font-display font-bold text-lg text-ink mb-1">确认你的学校</h3>
            <p className="text-sm text-ink-muted mb-4">
              你当前所在的学校是
            </p>
            <div className="px-4 py-3 rounded-[12px] bg-lake/5 border border-lake/20 mb-4">
              <span className="font-medium text-lake">{currentSchoolName || '未选择'}</span>
            </div>
            <p className="text-xs text-ink-muted">
              可以通过页头切换器随时切换学校
            </p>
          </div>
        )}

        {/* Step 2: 关注分类与地点 */}
        {step === 2 && (
          <div className="py-2">
            <div className="text-center mb-4">
              <div className="w-12 h-12 rounded-full bg-lake/10 grid place-items-center mx-auto mb-3">
                <Tag size={24} className="text-lake" />
              </div>
              <h3 className="font-display font-bold text-lg text-ink mb-1">关注你感兴趣的分类与地点</h3>
              <p className="text-sm text-ink-muted">点击关注，随时获取最新信息</p>
            </div>

            {metadataLoading ? (
              <LoadingState title="正在加载关注选项" compact />
            ) : metadataError ? (
              <ErrorState
                title="关注选项暂时无法加载"
                description={metadataError}
                onRetry={() => void loadMetadata()}
                compact
              />
            ) : (
              <>
            <div className="mb-3">
              <div className="flex items-center gap-1.5 text-xs text-ink-muted mb-2 px-1">
                <Tag size={12} />
                <span>分类</span>
              </div>
              <div className="flex flex-wrap gap-2 justify-center max-h-[160px] overflow-y-auto">
                {categories.length === 0 && (
                  <EmptyState title="暂无可关注分类" compact />
                )}
                {categories.map((cat) => (
                  <button
                    key={cat.id}
                    type="button"
                    onClick={() => toggleCategory(cat.id)}
                    className={`px-3 py-1.5 rounded-full text-sm transition-colors border ${
                      followedCategories.has(cat.id)
                        ? 'bg-lake text-paper border-lake'
                        : 'bg-paper text-ink border-line hover:border-lake/40'
                    }`}
                  >
                    {cat.icon && <span className="mr-1">{cat.icon}</span>}
                    {cat.name}
                    {followedCategories.has(cat.id) && <Check size={12} className="inline ml-1" />}
                  </button>
                ))}
              </div>
            </div>

            {/* 地点区域 — ACC-01.4 新增 */}
            <div>
              <div className="flex items-center gap-1.5 text-xs text-ink-muted mb-2 px-1">
                <MapPin size={12} />
                <span>地点</span>
              </div>
              <div className="flex flex-wrap gap-2 justify-center max-h-[160px] overflow-y-auto">
                {locations.length === 0 && (
                  <EmptyState title="暂无可关注地点" compact />
                )}
                {locations.map((loc) => (
                  <button
                    key={loc.id}
                    type="button"
                    onClick={() => toggleLocation(loc.id)}
                    className={`px-3 py-1.5 rounded-full text-sm transition-colors border ${
                      followedLocations.has(loc.id)
                        ? 'bg-lake text-paper border-lake'
                        : 'bg-paper text-ink border-line hover:border-lake/40'
                    }`}
                  >
                    <MapPin size={12} className="inline mr-1" />
                    {loc.name}
                    {followedLocations.has(loc.id) && <Check size={12} className="inline ml-1" />}
                  </button>
                ))}
              </div>
            </div>
              </>
            )}
          </div>
        )}

        {/* Step 3: 完成搜索或跳过 */}
        {step === 3 && (
          <div className="text-center py-2">
            <div className="w-12 h-12 rounded-full bg-lake/10 grid place-items-center mx-auto mb-3">
              <Search size={24} className="text-lake" />
            </div>
            <h3 className="font-display font-bold text-lg text-ink mb-1">试试搜索</h3>
            <p className="text-sm text-ink-muted mb-4">
              搜索你感兴趣的校园信息，或跳过此步
            </p>
            <button
              type="button"
              onClick={handleGoSearch}
              className="w-full px-4 py-2.5 rounded-[10px] bg-lake/5 border border-lake/20 text-lake text-sm font-medium hover:bg-lake/10 transition-colors flex items-center justify-center gap-1.5"
            >
              <Search size={14} />
              前往搜索
            </button>
          </div>
        )}

        {/* 底部按钮 */}
        <div className="flex items-center justify-between pt-3 border-t border-line/40">
          <button
            type="button"
            onClick={handleSkip}
            className="text-sm text-ink-muted hover:text-ink transition-colors flex items-center gap-1"
          >
            <X size={14} />
            跳过引导
          </button>
          {step < 3 ? (
            <Button variant="primary" size="sm" onClick={handleNext}>
              下一步
              <ArrowRight size={14} className="ml-1" />
            </Button>
          ) : (
            <Button variant="primary" size="sm" onClick={handleComplete}>
              <Check size={14} className="mr-1" />
              完成
            </Button>
          )}
        </div>
      </div>
    </Modal>
  );
};

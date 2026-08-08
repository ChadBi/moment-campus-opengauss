import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  X,
  Image as ImageIcon,
  AlertTriangle,
  RotateCcw,
  Trash2,
  Send,
  Sparkles,
  Check,
  Info,
  ShieldAlert,
} from 'lucide-react';
import { postsApi } from '../services/posts';
import { categoriesApi } from '../services/categories';
import type {
  CategoryListItem,
  LocationListItem,
} from '../services/categories';
import { uploadApi } from '../services/upload';
import { useCampusStore } from '../store/useCampusStore';
import { useAuthStore } from '../store/useAuthStore';
import { canWriteInCurrentSchool } from '../utils/campus-permission';
import { useUIStore } from '../store/useUIStore';
import { Button } from './ui/Button';
import { Input } from './ui/Input';
import { Loading } from './ui/Loading';
import { ErrorState, LoadingState } from './state';
import type { AIPublishSuggestionResponse } from '../types';

/**
 * PUB-01.1: 统一发布表单（共享子组件）
 *
 * Task 3.1 调整：
 *   - 移除 tags / post_type / activity_start_at / activity_end_at 字段（模型已删除/字段已下线）
 *   - 「有效期」重命名为「信息截止时间」
 *   - 「失物类型」改为条件渲染：仅当 selectedCategory.code === 'lost_found' 时显示
 *   - 「地点」改为非必填，新增「在地图上选择位置」按钮（弹窗内嵌 MapLocationPicker）
 *   - 经纬度改为只读展示（由地图选点自动填充）
 *
 * 合并原 PublishPage 与 MapPage 发帖面板的表单逻辑：
 *   - 分类 / 地点全部来自 API（带 X-School-Code 头，按当前学校过滤）
 *   - 图片预览（多图，最多 9 张）+ 信息截止时间 + 联系方式 + 失物类型 + 匿名
 *   - 地点选择：本校已核验地点下拉 + 新增地点（地图选点，进 is_verified=false 队列）
 *   - 草稿恢复：按 用户 + 学校 分键 localStorage，自动保存（防抖 1s）+ 离开页前同步写入 + 恢复横幅
 *   - 发布成功后由调用方通过 onSuccess 回调决定跳转（PUB-01.3：默认跳 /profile）
 *
 * 两种 UI 风格：
 *   - variant='page'  ：PublishPage 用，Card + Input 组件 + 宽松间距
 *   - variant='panel' ：MapPage 侧滑面板用，紧凑原生 input + 紧凑间距
 *
 * 地图点选发帖：调用方传入 defaultLocationLat/Lng/Name，PostForm 初始化新地点坐标并标记只读。
 */

const MAX_IMAGES = 9;
// UX-01.4: 自动保存策略
//   - DRAFT_AUTOSAVE_DELAY_MS：输入变化后防抖 1s 写入（保持响应性）
//   - DRAFT_AUTOSAVE_INTERVAL_MS：固定 5s 周期写入（保证离开前最近 5s 内有保存）
const DRAFT_AUTOSAVE_DELAY_MS = 1000;
const DRAFT_AUTOSAVE_INTERVAL_MS = 5000;

interface PublishFormState {
  title: string;
  content: string;
  category_id: number | null;
  location_id: number | null;
  is_anonymous: boolean;
  /** 【新版】一张图同时携带原图 + 缩略图 URL；提交时传给后端 images 字段，详情页缩略带宽优化才能生效 */
  images: Array<{ image_url: string; thumbnail_url?: string }>;
  expire_at: string; // datetime-local 字符串（信息截止时间）
  contact_info: string;
  lost_type: '' | 'lost' | 'found';
  // ORG-01: publisher_id 字段已随发布主体功能移除
}

const INITIAL_FORM: PublishFormState = {
  title: '',
  content: '',
  category_id: null,
  location_id: null,
  is_anonymous: false,
  images: [],
  expire_at: '',
  contact_info: '',
  lost_type: '',
};

/** 把 datetime-local 字符串转换为后端期望的 ISO 字符串；空值返回 undefined */
function toIso(datetimeLocal: string): string | undefined {
  if (!datetimeLocal) return undefined;
  const d = new Date(datetimeLocal);
  if (Number.isNaN(d.getTime())) return undefined;
  return d.toISOString();
}

/** PUB-02: 把后端 ISO 时间转换为 datetime-local 输入框字符串（本地时区）；空值返回 '' */
function toDatetimeLocal(iso?: string): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

// ============ ACC-01.4: 草稿 localStorage 持久化 ============
interface PersistedDraft {
  form: PublishFormState;
  savedAt: string; // ISO 时间戳
}

function buildDraftStorageKey(userId: number | undefined, schoolId: number | null): string {
  return `publish_draft::u${userId ?? 'anon'}::s${schoolId ?? 'none'}`;
}

function isFormEffectivelyEmpty(form: PublishFormState): boolean {
  return (
    !form.title.trim() &&
    !form.content.trim() &&
    form.images.length === 0 &&
    !form.location_id &&
    !form.contact_info.trim()
  );
}

function loadDraft(key: string): PersistedDraft | null {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as PersistedDraft;
    if (!parsed || !parsed.form || !parsed.savedAt) return null;
    // DRAFT-MIGRATION-1: 2026-08-07 从 image_urls:string[] 迁移到 images:{image_url,thumbnail_url}[]
    const form = parsed.form as PublishFormState & { image_urls?: string[] };
    if (form.images == null || form.images.length === 0) {
      if (Array.isArray(form.image_urls) && form.image_urls.length > 0) {
        form.images = form.image_urls.map((u) => ({ image_url: u, thumbnail_url: undefined }));
      } else if (!Array.isArray(form.images)) {
        form.images = [];
      }
      // 写回新字段（可选）：避免下次再迁移
      delete (form as { image_urls?: unknown }).image_urls;
    }
    if (isFormEffectivelyEmpty(parsed.form)) return null;
    return parsed;
  } catch {
    return null;
  }
}

function saveDraft(key: string, form: PublishFormState): void {
  if (isFormEffectivelyEmpty(form)) {
    localStorage.removeItem(key);
    return;
  }
  const payload: PersistedDraft = {
    form,
    savedAt: new Date().toISOString(),
  };
  try {
    localStorage.setItem(key, JSON.stringify(payload));
  } catch {
    // 配额不足或隐私模式：静默失败，不阻塞发布流程
  }
}

function clearDraft(key: string): void {
  localStorage.removeItem(key);
}

function formatSavedAt(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return '';
  }
}

/** 根据 variant 提供差异化样式（page 宽松 / panel 紧凑） */
function getVariantStyles(variant: 'page' | 'panel') {
  if (variant === 'panel') {
    return {
      formSpacing: 'space-y-3',
      label: 'block text-sm font-medium text-ink mb-1.5',
      textarea:
        'w-full px-3.5 py-2.5 bg-white/78 border border-line rounded-md text-sm text-ink placeholder:text-ink-muted/70 focus:outline-none focus:bg-white focus:border-lake transition-all resize-none',
      // 2026-08-07 统一 select 美化：改走全局 .select-nice-sm（紧凑尺寸）
      select: 'select-nice-sm',
      catChip: 'flex items-center gap-1 px-2 py-1.5 rounded-md text-[11px] font-medium transition-all',
      catChipActive: 'bg-lake text-white shadow-lake',
      catChipInactive: 'bg-mist text-ink-sub hover:bg-line',
      typeChip: 'px-2.5 py-1.5 rounded-md text-[11px] font-medium transition-all',
      // 2.2.5 修复：panel 侧滑面板内按钮也需高于 MobileNav（z-30）以防被遮挡
      submitRow: 'flex flex-col gap-2 pt-1 relative z-40 pb-6 md:pb-1',
      draftFull: true,
    };
  }
  return {
    formSpacing: 'space-y-4',
    label: 'block text-sm font-medium text-ink mb-1.5 font-sans',
    textarea:
      'w-full px-3.5 py-3 bg-paper border border-line rounded-[10px] text-sm text-ink placeholder:text-ink-muted/60 focus:outline-none focus:border-lake transition-colors resize-none',
    // 2026-08-07 统一 select 美化：改走全局 .select-nice（标准 40px）
    select: 'select-nice',
    catChip: 'flex items-center gap-1.5 px-3 py-2 rounded-[10px] text-xs font-medium transition-all',
    catChipActive: 'bg-lake text-white shadow-sm',
    catChipInactive: 'bg-paper-hover text-ink-sub hover:bg-line',
    typeChip: 'px-3 py-1.5 rounded-[10px] text-xs font-medium transition-all',
    // 2.2.5 修复：提交审核按钮容器添加 padding-bottom: 96px（仅移动端）
    //   + relative z-40（高于 MobileNav 的 z-30），确保按钮不被底部固定导航栏遮挡
    submitRow: 'flex gap-2 pt-2 relative z-40 pb-24 md:pb-2',
    submitFlex: '1',
    draftFull: false,
  };
}

export interface PostFormProps {
  /** UI 风格：page=完整页（Card+Input 组件），panel=侧滑面板（紧凑原生 input） */
  variant?: 'page' | 'panel';
  /** 提交成功回调（status=draft|pending）；调用方负责跳转/关闭面板 */
  onSuccess?: (status: 'draft' | 'pending') => void;
  /** 取消回调（不传则隐藏取消按钮） */
  onCancel?: () => void;
  /** 是否显示草稿恢复横幅（默认 true） */
  enableDraftBanner?: boolean;
  /** 是否显示"存为草稿"按钮（默认 true） */
  showDraftButton?: boolean;
  /** 是否显示"取消"按钮（默认 true） */
  showCancelButton?: boolean;
  /** 提交按钮文案 */
  submitLabel?: string;
  /** 草稿按钮文案 */
  draftLabel?: string;
  /**
   * PUB-02: 编辑已有帖子（草稿）的 ID。
   * 传入后表单进入编辑模式：加载并预填该帖子，提交走 update（+ 可选 draft→pending 流转），
   * 且停用 localStorage 草稿恢复/自动保存（避免与服务器端草稿互相覆盖）。
   */
  editPostId?: number;
}

const PostForm: React.FC<PostFormProps> = ({
  variant = 'page',
  onSuccess,
  onCancel,
  enableDraftBanner = true,
  showDraftButton = true,
  showCancelButton = true,
  submitLabel,
  draftLabel,
  editPostId,
}) => {
  const currentSchoolId = useCampusStore((s) => s.currentSchoolId);
  const allowAnonymous = useCampusStore((s) => s.publicSettings?.allow_anonymous ?? true);
  const { user } = useAuthStore();
  const { showToast } = useUIStore();

  const isAdmin = user?.role === 'admin' || user?.role === 'super_admin';
  const canAnonymous = allowAnonymous || isAdmin;
  const canWrite = canWriteInCurrentSchool(user, currentSchoolId);

  // PUB-02: 编辑模式标志与按钮文案（编辑草稿时"存为草稿"语义为保存修改）
  const isEditMode = editPostId != null;
  const effectiveSubmitLabel = submitLabel ?? '提交审核';
  const effectiveDraftLabel = draftLabel ?? (isEditMode ? '保存修改' : '存为草稿');

  const vs = getVariantStyles(variant);

  const getInitialForm = useMemo(() => {
    return (): PublishFormState => ({ ...INITIAL_FORM });
  }, []);

  const [formData, setFormData] = useState<PublishFormState>(getInitialForm);
  const [categories, setCategories] = useState<CategoryListItem[]>([]);
  const [locations, setLocations] = useState<LocationListItem[]>([]);
  const [metaLoading, setMetaLoading] = useState(true);
  const [metaError, setMetaError] = useState<string | null>(null);

  // ORG-01.3: 发布主体与公共模板功能已下线（templates / appliedTemplateId 状态移除）

  const [uploading, setUploading] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  // AI-03: AI 辅助发布建议状态
  const [aiSuggesting, setAiSuggesting] = useState(false);
  const [aiSuggestion, setAiSuggestion] = useState<AIPublishSuggestionResponse | null>(null);
  const [aiSuggestionError, setAiSuggestionError] = useState<string | null>(null);
  // 已采纳的字段记录，便于面板显示"已采纳"状态
  const [adoptedFields, setAdoptedFields] = useState<Set<string>>(new Set());

  // ACC-01.4: 草稿恢复状态
  const draftStorageKey = useMemo(
    () => buildDraftStorageKey(user?.id, currentSchoolId),
    [user?.id, currentSchoolId]
  );
  const [pendingDraft, setPendingDraft] = useState<PersistedDraft | null>(null);
  const [draftRestored, setDraftRestored] = useState(false);

  // PUB-02: 编辑模式加载状态
  const [editLoading, setEditLoading] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const formDataRef = useRef<PublishFormState>(formData);
  const draftKeyRef = useRef<string>(draftStorageKey);

  // 保持 ref 与最新值同步，供 beforeunload 使用
  useEffect(() => {
    formDataRef.current = formData;
  }, [formData]);
  useEffect(() => {
    draftKeyRef.current = draftStorageKey;
  }, [draftStorageKey]);

  const loadMetadata = useCallback(async () => {
    setMetaLoading(true);
    setMetaError(null);
    try {
      const [cats, locs] = await Promise.all([
        categoriesApi.listCategories(),
        categoriesApi.listLocations(),
      ]);
      setCategories(cats);
      setLocations(locs);
      setFormData((prev) => ({
        ...prev,
        category_id: prev.category_id ?? cats[0]?.id ?? null,
      }));
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      setMetaError(e?.response?.data?.detail || '加载分类 / 地点失败，请重试');
    } finally {
      setMetaLoading(false);
    }
  }, []);

  useEffect(() => {
    void Promise.resolve().then(loadMetadata);
  }, [currentSchoolId, loadMetadata]);

  // 切换学校时清空已选地点（避免跨校残留）
  useEffect(() => {
    void Promise.resolve().then(() => {
      setFormData((prev) => ({
        ...prev,
        location_id: null,
      }));
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentSchoolId]);

  // 当 !canAnonymous 时，强制 is_anonymous=false（切校/设置变更的边界兜底）
  useEffect(() => {
    if (!canAnonymous) {
      setFormData((prev) => {
        if (prev.is_anonymous) {
          return { ...prev, is_anonymous: false };
        }
        return prev;
      });
    }
  }, [canAnonymous]);

  // PUB-02: 编辑模式 — 加载已有帖子并预填表单（作者可见自己所有状态，含草稿）
  useEffect(() => {
    if (!isEditMode) return;
    let cancelled = false;
    void Promise.resolve().then(() => {
      if (cancelled) return;
      setEditLoading(true);
      setEditError(null);
    });
    postsApi
      .getPost(editPostId)
      .then((post) => {
        if (cancelled) return;
        setFormData({
          title: post.title,
          content: post.content,
          category_id: post.category_id ?? null,
          location_id: post.location_id ?? null,
          is_anonymous: post.is_anonymous,
          images: (post.images ?? [])
            .slice()
            .sort((a, b) => a.sort_order - b.sort_order)
            .map((img) => ({
              image_url: img.image_url,
              thumbnail_url: img.thumbnail_url,
            })),
          expire_at: toDatetimeLocal(post.expire_at),
          contact_info: post.contact_info ?? '',
          lost_type: (post.lost_type as '' | 'lost' | 'found') ?? '',
        });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const e = err as { response?: { data?: { detail?: string } } };
        setEditError(e?.response?.data?.detail || '加载草稿失败，请返回"我的发布"重试');
      })
      .finally(() => {
        if (!cancelled) setEditLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editPostId]);

  // ACC-01.4: 草稿恢复提示 — 仅在首次挂载且当前表单为空时检测（编辑模式不恢复本地草稿）
  useEffect(() => {
    if (draftRestored) return;
    const existing = isEditMode ? null : loadDraft(draftStorageKey);
    void Promise.resolve().then(() => {
      if (existing && isFormEffectivelyEmpty(formData)) {
        setPendingDraft(existing);
      }
      setDraftRestored(true);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draftStorageKey]);

  // ACC-01.4: 表单变化时自动保存（防抖 1s；编辑模式不写本地草稿，避免覆盖服务器端草稿）
  useEffect(() => {
    if (!draftRestored) return; // 恢复提示未就绪前不写回，避免覆盖旧草稿
    if (isEditMode) return;
    const timer = window.setTimeout(() => {
      saveDraft(draftStorageKey, formData);
    }, DRAFT_AUTOSAVE_DELAY_MS);
    return () => window.clearTimeout(timer);
  }, [formData, draftStorageKey, draftRestored, isEditMode]);

  // UX-01.4: 固定 5s 周期自动保存（防止用户长时间未输入但页面停留造成的丢失）
  // 即使无新输入，每 5s 写入一次最新表单状态；编辑模式跳过。
  useEffect(() => {
    if (!draftRestored) return;
    if (isEditMode) return;
    const interval = window.setInterval(() => {
      saveDraft(draftStorageKey, formDataRef.current);
    }, DRAFT_AUTOSAVE_INTERVAL_MS);
    return () => window.clearInterval(interval);
  }, [draftStorageKey, draftRestored, isEditMode]);

  // UX-01.4: React Router 单页应用内路由切换时同步保存（beforeunload 仅在整页卸载时触发）
  useEffect(() => {
    if (!draftRestored) return;
    if (isEditMode) return;
    // 使用 visibilitychange 捕获标签页隐藏/切换（移动端切换 App 也会触发）
    const handler = () => {
      if (document.visibilityState === 'hidden') {
        saveDraft(draftKeyRef.current, formDataRef.current);
      }
    };
    document.addEventListener('visibilitychange', handler);
    return () => document.removeEventListener('visibilitychange', handler);
  }, [draftRestored, isEditMode]);

  // ACC-01.4: 离开页面前立即保存（覆盖式同步写入；编辑模式跳过）
  useEffect(() => {
    const handler = () => {
      if (editPostId != null) return;
      saveDraft(draftKeyRef.current, formDataRef.current);
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleRestoreDraft = () => {
    if (!pendingDraft) return;
    setFormData(pendingDraft.form);
    setPendingDraft(null);
    showToast(`已恢复未完成草稿（保存于 ${formatSavedAt(pendingDraft.savedAt)}）`, 'info');
  };

  const handleDiscardDraft = () => {
    clearDraft(draftStorageKey);
    setPendingDraft(null);
    // 丢弃后回到初始值（含地图点选坐标）
    setFormData(getInitialForm());
    showToast('已丢弃草稿', 'info');
  };

  const selectedCategory = useMemo(
    () => categories.find((c) => c.id === formData.category_id) || null,
    [categories, formData.category_id]
  );

  const verifiedLocations = useMemo(
    () => locations.filter((l) => l.is_verified),
    [locations]
  );
  const unverifiedLocations = useMemo(
    () => locations.filter((l) => !l.is_verified),
    [locations]
  );

  const handleFieldChange = <K extends keyof PublishFormState>(
    key: K,
    value: PublishFormState[K]
  ) => {
    setFormData((prev) => ({ ...prev, [key]: value }));
  };

  const handleCategorySelect = (id: number) => {
    handleFieldChange('category_id', id);
  };

  // ============ ORG-01.3: 发布模板一键补全（已下线，整段移除） ============

  const handleLocationSelect = (idStr: string) => {
    if (!idStr) {
      handleFieldChange('location_id', null);
      return;
    }
    handleFieldChange('location_id', Number(idStr));
  };

  // ============ 图片上传 ============
  const handleImageChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    if (files.length === 0) return;
    if (formData.images.length + files.length > MAX_IMAGES) {
      showToast(`最多上传 ${MAX_IMAGES} 张图片`, 'warning');
      return;
    }
    setUploading(true);
    try {
      // 对象数组：{image_url, thumbnail_url} 同时携带，写库后详情缩略带宽优化才真正生效
      const uploaded: Array<{ image_url: string; thumbnail_url?: string }> = [];
      for (const file of files) {
        if (file.size > 5 * 1024 * 1024) {
          showToast(`${file.name} 超过 5MB`, 'warning');
          continue;
        }
        const resp = await uploadApi.uploadImage(file);
        uploaded.push({ image_url: resp.url, thumbnail_url: resp.thumbnail_url });
      }
      if (uploaded.length > 0) {
        handleFieldChange('images', [...formData.images, ...uploaded]);
      }
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      showToast(e?.response?.data?.detail || '图片上传失败', 'error');
    } finally {
      setUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const handleRemoveImage = (imageUrl: string) => {
    handleFieldChange(
      'images',
      formData.images.filter((img) => img.image_url !== imageUrl)
    );
  };

  // ============ AI-03: AI 辅助发布建议 ============
  const handleAISuggest = async () => {
    // 失败不阻塞：错误以提示形式展示，不影响手动发布
    if (aiSuggesting) return;
    setAiSuggesting(true);
    setAiSuggestionError(null);
    // 复用已有结果时不重新请求；用户已显式点击才覆盖
    try {
      const payload = {
        title: formData.title.trim(),
        content: formData.content.trim(),
        category_id: formData.category_id,
        location_id: formData.location_id,
        contact_info: formData.contact_info.trim() || null,
        lost_type: formData.lost_type || null,
        expire_at: toIso(formData.expire_at) ?? null,
      };
      const resp = await postsApi.aiSuggest(payload);
      setAiSuggestion(resp);
      setAdoptedFields(new Set());
      if (resp.fallback) {
        // 降级：仅展示提示，不阻塞发布
        showToast(
          resp.fallback_reason || 'AI 建议暂时不可用，已切换为仅展示敏感检测结果',
          'info'
        );
      } else {
        showToast('AI 建议已生成，可逐项确认采纳', 'success');
      }
    } catch (err: unknown) {
      // 失败不阻塞：仅记录错误，不抛出
      const e = err as { response?: { data?: { detail?: string } } };
      const msg = e?.response?.data?.detail || 'AI 建议获取失败，可继续手动填写';
      setAiSuggestionError(msg);
      showToast(msg, 'warning');
    } finally {
      setAiSuggesting(false);
    }
  };

  /** 采纳建议标题（覆盖原文标题） */
  const adoptTitle = () => {
    const t =
      aiSuggestion?.suggestions?.optimized_title || aiSuggestion?.suggestions?.title;
    if (!t) return;
    handleFieldChange('title', t);
    setAdoptedFields((prev) => new Set(prev).add('title'));
    showToast(
      aiSuggestion?.suggestions?.optimized_title ? '已采纳优化标题' : '已采纳建议标题',
      'success'
    );
  };

  /** 采纳优化后的正文（覆盖原文正文） */
  const adoptContent = () => {
    const content = aiSuggestion?.suggestions?.optimized_content;
    if (!content) return;
    handleFieldChange('content', content);
    setAdoptedFields((prev) => new Set(prev).add('optimized_content'));
    showToast('已采纳优化正文', 'success');
  };

  /** 采纳建议分类（必须为白名单内的 category_id） */
  const adoptCategory = () => {
    const cid = aiSuggestion?.suggestions?.category_id;
    if (cid == null) return;
    handleFieldChange('category_id', cid);
    setAdoptedFields((prev) => new Set(prev).add('category'));
    showToast('已采纳建议分类', 'success');
  };

  /** 采纳建议默认有效期（按天数计算 expire_at） */
  const adoptValidity = () => {
    const days = aiSuggestion?.suggestions?.default_validity_days;
    if (!days || days < 1) return;
    const d = new Date();
    d.setDate(d.getDate() + days);
    // datetime-local 字符串格式
    const pad = (n: number) => String(n).padStart(2, '0');
    const dtLocal = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
    handleFieldChange('expire_at', dtLocal);
    setAdoptedFields((prev) => new Set(prev).add('validity'));
    showToast(`已采纳建议有效期（${days} 天）`, 'success');
  };

  /** 关闭 AI 建议面板 */
  const dismissAISuggestion = () => {
    setAiSuggestion(null);
    setAiSuggestionError(null);
    setAdoptedFields(new Set());
  };

  // ============ 提交 ============
  const validate = (): string | null => {
    if (!formData.title.trim()) return '请填写标题';
    if (formData.title.length < 5 || formData.title.length > 100) {
      return '标题长度必须在 5-100 字符之间';
    }
    if (!formData.content.trim()) return '请填写内容';
    if (formData.content.length < 10 || formData.content.length > 5000) {
      return '内容长度必须在 10-5000 字符之间';
    }
    if (!formData.category_id) return '请选择分类';
    return null;
  };

  const handleSubmit = async (e: React.FormEvent, status: 'draft' | 'pending') => {
    e.preventDefault();
    if (!canWrite) {
      showToast('当前学校仅支持浏览，请切回注册学校后再发布内容', 'warning');
      return;
    }
    const validationError = validate();
    if (validationError) {
      showToast(validationError, 'warning');
      return;
    }
    setSubmitting(true);
    try {
      const payload = {
        title: formData.title.trim(),
        content: formData.content.trim(),
        category_id: formData.category_id as number,
        location_id: formData.location_id ?? undefined,
        is_anonymous: formData.is_anonymous,
        // 新版 images 字段（原图+缩略图 URL 一起带）；后端同时兼容旧版 image_urls 字符串数组
        images: formData.images.length > 0 ? formData.images : undefined,
        expire_at: toIso(formData.expire_at),
        contact_info: formData.contact_info.trim() || undefined,
        lost_type: formData.lost_type || undefined,
      };
      if (isEditMode) {
        // PUB-02: 编辑模式 — 先保存修改；提交审核时再走 draft → pending 状态流转
        await postsApi.updatePost(editPostId, payload);
        if (status === 'pending') {
          await postsApi.transitionPost(editPostId, 'pending');
        }
      } else {
        // ORG-01: publisher_id 已随发布主体功能移除，创建时仅传必要字段
        await postsApi.createPost({
          ...payload,
          status,
        });
      }
      showToast(
        status === 'draft'
          ? isEditMode
            ? '修改已保存，可继续编辑或提交审核'
            : '草稿已保存，可在"我的发布"继续编辑'
          : '已提交审核，可在"我的发布"查看进度',
        'success'
      );
      // ACC-01.4：提交成功后清除本地草稿（避免下次进入误恢复）
      clearDraft(draftStorageKey);
      // 通知调用方
      onSuccess?.(status);
    } catch (error: unknown) {
      const e = error as { response?: { data?: { detail?: string } } };
      showToast(e?.response?.data?.detail || '操作失败，请稍后重试', 'error');
    } finally {
      setSubmitting(false);
    }
  };

  // ============ 渲染 ============
  if (metaLoading || editLoading) {
    return (
      <div className={variant === 'page' ? 'py-16' : 'py-8'}>
        <LoadingState title={editLoading ? '正在加载草稿' : '正在加载发布元数据'} compact={variant === 'panel'} />
      </div>
    );
  }

  if (editError) {
    return (
      <div className="py-4">
        <div className="text-center py-10">
          <AlertTriangle size={28} className="text-danger mx-auto mb-3" />
          <p className="text-ink-sub text-sm mb-4">{editError}</p>
          {onCancel ? (
            <Button variant="secondary" size="sm" onClick={onCancel}>
              返回
            </Button>
          ) : null}
        </div>
      </div>
    );
  }

  if (!canWrite) {
    return (
      <div className="rounded-[12px] border border-lake/20 bg-lake/[0.04] px-4 py-8 text-center">
        <p className="font-medium text-ink">当前学校仅支持浏览</p>
        <p className="mt-1 text-sm text-ink-muted">请切回注册学校后再发布内容。</p>
      </div>
    );
  }

  if (metaError) {
    return (
      <div className={variant === 'page' ? 'py-4' : 'py-4 px-4'}>
        <ErrorState
          title="发布选项暂时无法加载"
          description={metaError}
          onRetry={() => void loadMetadata()}
          compact={variant === 'panel'}
        />
      </div>
    );
  }

  return (
    <div>
      {/* ACC-01.4: 草稿恢复横幅 */}
      {enableDraftBanner && pendingDraft && (
        <div className="mb-3 rounded-[12px] border border-lamp/40 bg-lamp/8 px-4 py-3 flex items-start gap-3">
          <RotateCcw size={18} className="text-lake flex-shrink-0 mt-0.5" />
          <div className="flex-1 min-w-0">
            <p className="text-sm text-ink font-medium">
              发现未完成的草稿
              {pendingDraft.savedAt && (
                <span className="text-ink-muted ml-1 font-normal">
                  （保存于 {formatSavedAt(pendingDraft.savedAt)}）
                </span>
              )}
            </p>
            <p className="text-xs text-ink-muted mt-0.5">
              会话过期或离开页面前的内容已保留，可恢复继续编辑或丢弃。
            </p>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            <Button variant="primary" size="sm" onClick={handleRestoreDraft}>
              恢复
            </Button>
            <Button variant="text" size="sm" onClick={handleDiscardDraft}>
              <Trash2 size={14} className="mr-1" />
              丢弃
            </Button>
          </div>
        </div>
      )}

      <form
        onSubmit={(e) => handleSubmit(e, 'pending')}
        className={vs.formSpacing}
        aria-label="发布信息表单"
      >
        {/* AI-03: AI 辅助发布建议按钮 + 采纳面板 */}
        <div className="rounded-[12px] border border-lamp/30 bg-gradient-to-br from-lamp/8 to-lake/5 px-4 py-3">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              <Sparkles size={16} className="text-lake flex-shrink-0" />
              <div className="min-w-0">
                <p className="text-sm text-ink font-medium truncate">AI 辅助发布建议</p>
                <p className="text-[11px] text-ink-muted truncate">
                  基于草稿生成标题、正文、分类、有效期及遗漏/敏感提醒
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
              {aiSuggestion ? (
                <Button
                  type="button"
                  variant="text"
                  size="sm"
                  onClick={dismissAISuggestion}
                >
                  关闭
                </Button>
              ) : null}
              <Button
                type="button"
                variant="primary"
                size="sm"
                loading={aiSuggesting}
                icon={!aiSuggesting ? <Sparkles size={14} /> : undefined}
                onClick={handleAISuggest}
                disabled={aiSuggesting}
              >
                {aiSuggestion ? '重新生成' : 'AI 建议'}
              </Button>
            </div>
          </div>
          {aiSuggesting ? (
            <div className="mt-2 flex items-center gap-2 text-xs text-ink-muted">
              <Loading size="sm" />
              <span>正在生成建议...</span>
            </div>
          ) : null}
          {aiSuggestionError ? (
            <div className="mt-2 flex items-start gap-2 text-xs text-danger bg-danger/8 rounded-md px-3 py-2">
              <AlertTriangle size={14} className="flex-shrink-0 mt-0.5" />
              <div className="flex-1">
                <p>{aiSuggestionError}</p>
                <p className="text-ink-muted mt-0.5">
                  AI 建议获取失败，可继续手动填写发布，不影响后续流程。
                </p>
              </div>
            </div>
          ) : null}
          {aiSuggestion ? (
            <div className="mt-3 space-y-3">
              {/* 降级提示 */}
              {aiSuggestion.fallback ? (
                <div className="flex items-start gap-2 text-xs text-[#9a6b00] bg-lamp/12 rounded-md px-3 py-2 border border-lamp/30">
                  <Info size={14} className="flex-shrink-0 mt-0.5" />
                  <div className="flex-1">
                    <p className="font-medium">
                      {aiSuggestion.fallback_reason || 'AI 服务暂时不可用'}
                    </p>
                    <p className="text-ink-muted mt-0.5">
                      已返回确定性检测结果（敏感信息/遗漏提示），仍可继续手动发布。
                    </p>
                  </div>
                </div>
              ) : null}

              {/* 结构化建议（suggestions） */}
              {aiSuggestion.suggestions ? (
                <div className="space-y-2">
                  {/* 建议标题 */}
                  {aiSuggestion.suggestions.optimized_title || aiSuggestion.suggestions.title ? (
                    <div className="bg-white/60 rounded-md px-3 py-2 border border-line">
                      <div className="flex items-center justify-between gap-2">
                        <div className="min-w-0 flex-1">
                          <p className="text-[11px] text-ink-muted mb-0.5">
                            {aiSuggestion.suggestions.optimized_title ? '优化后的标题' : '建议标题'}
                          </p>
                          <p className="text-sm text-ink break-words">
                            {aiSuggestion.suggestions.optimized_title || aiSuggestion.suggestions.title}
                          </p>
                        </div>
                        {adoptedFields.has('title') ? (
                          <span className="text-[11px] text-grass flex items-center gap-0.5 flex-shrink-0">
                            <Check size={12} /> 已采纳
                          </span>
                        ) : (
                          <Button
                            type="button"
                            variant="secondary"
                            size="sm"
                            onClick={adoptTitle}
                          >
                            采纳
                          </Button>
                        )}
                      </div>
                    </div>
                  ) : null}

                  {/* 优化正文 */}
                  {aiSuggestion.suggestions.optimized_content ? (
                    <div className="bg-white/60 rounded-md px-3 py-2 border border-line">
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0 flex-1">
                          <p className="text-[11px] text-ink-muted mb-0.5">优化后的正文</p>
                          <p className="text-sm text-ink whitespace-pre-wrap break-words">
                            {aiSuggestion.suggestions.optimized_content}
                          </p>
                        </div>
                        {adoptedFields.has('optimized_content') ? (
                          <span className="text-[11px] text-grass flex items-center gap-0.5 flex-shrink-0">
                            <Check size={12} /> 已采纳
                          </span>
                        ) : (
                          <Button
                            type="button"
                            variant="secondary"
                            size="sm"
                            onClick={adoptContent}
                          >
                            采纳
                          </Button>
                        )}
                      </div>
                    </div>
                  ) : null}

                  {/* 建议分类 */}
                  {aiSuggestion.suggestions.category_id != null ? (
                    <div className="bg-white/60 rounded-md px-3 py-2 border border-line">
                      <div className="flex items-center justify-between gap-2">
                        <div className="min-w-0 flex-1">
                          <p className="text-[11px] text-ink-muted mb-0.5">建议分类</p>
                          <p className="text-sm text-ink break-words">
                            {aiSuggestion.suggestions.category ||
                              categories.find(
                                (c) => c.id === aiSuggestion.suggestions?.category_id
                              )?.name ||
                              `分类ID ${aiSuggestion.suggestions.category_id}`}
                          </p>
                        </div>
                        {adoptedFields.has('category') ? (
                          <span className="text-[11px] text-grass flex items-center gap-0.5 flex-shrink-0">
                            <Check size={12} /> 已采纳
                          </span>
                        ) : (
                          <Button
                            type="button"
                            variant="secondary"
                            size="sm"
                            onClick={adoptCategory}
                          >
                            采纳
                          </Button>
                        )}
                      </div>
                    </div>
                  ) : null}

                  {/* 建议默认有效期 */}
                  {aiSuggestion.suggestions.default_validity_days ? (
                    <div className="bg-white/60 rounded-md px-3 py-2 border border-line">
                      <div className="flex items-center justify-between gap-2">
                        <div className="min-w-0 flex-1">
                          <p className="text-[11px] text-ink-muted mb-0.5">建议默认有效期</p>
                          <p className="text-sm text-ink">
                            {aiSuggestion.suggestions.default_validity_days} 天
                          </p>
                        </div>
                        {adoptedFields.has('validity') ? (
                          <span className="text-[11px] text-grass flex items-center gap-0.5 flex-shrink-0">
                            <Check size={12} /> 已采纳
                          </span>
                        ) : (
                          <Button
                            type="button"
                            variant="secondary"
                            size="sm"
                            onClick={adoptValidity}
                          >
                            采纳
                          </Button>
                        )}
                      </div>
                    </div>
                  ) : null}
                </div>
              ) : null}

              {/* 遗漏信息提示 */}
              {aiSuggestion.missing_info.length > 0 ? (
                <div className="bg-lamp/8 rounded-md px-3 py-2 border border-lamp/20">
                  <div className="flex items-start gap-2">
                    <Info size={14} className="text-[#9a6b00] flex-shrink-0 mt-0.5" />
                    <div className="flex-1 min-w-0">
                      <p className="text-[11px] font-medium text-[#9a6b00] mb-1">遗漏信息提示</p>
                      <ul className="space-y-1">
                        {aiSuggestion.missing_info.map((m, idx) => (
                          <li
                            key={idx}
                            className="text-xs text-ink-sub flex items-start gap-1.5"
                          >
                            <span className="text-lamp mt-0.5">·</span>
                            <span className="flex-1 break-words">{m}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </div>
              ) : null}

              {/* 敏感信息提醒 */}
              {aiSuggestion.sensitive_warnings.length > 0 ? (
                <div className="bg-danger/8 rounded-md px-3 py-2 border border-danger/20">
                  <div className="flex items-start gap-2">
                    <ShieldAlert size={14} className="text-danger flex-shrink-0 mt-0.5" />
                    <div className="flex-1 min-w-0">
                      <p className="text-[11px] font-medium text-danger mb-1">敏感信息提醒</p>
                      <ul className="space-y-1">
                        {aiSuggestion.sensitive_warnings.map((s, idx) => (
                          <li
                            key={idx}
                            className="text-xs text-ink-sub flex items-start gap-1.5"
                          >
                            <span className="text-danger mt-0.5">·</span>
                            <span className="flex-1 break-words">{s}</span>
                          </li>
                        ))}
                      </ul>
                      {Object.keys(aiSuggestion.sensitive_findings).length > 0 ? (
                        <p className="text-[10px] text-ink-muted mt-1.5">
                          命中类型：
                          {Object.keys(aiSuggestion.sensitive_findings).join(' / ')}
                        </p>
                      ) : null}
                    </div>
                  </div>
                </div>
              ) : null}

              {/* 提示文案 */}
              <p className="text-[10px] text-ink-muted">
                建议仅供参考，是否采纳由您决定。AI 不修改原文，不影响状态/坐标/审核流程。
              </p>
            </div>
          ) : null}
        </div>

        {/* ORG-01.3: 发布模板 UI 已随发布主体功能移除 */}

        {/* 标题 */}
        <Input
          label="标题"
          name="title"
          type="text"
          value={formData.title}
          onChange={(e) => handleFieldChange('title', e.target.value)}
          placeholder="请输入标题（5-100 字符）"
          maxLength={100}
          required
        />

        {/* 分类（动态来自 API） */}
        <div role="group" aria-labelledby="category-label">
          <label id="category-label" className={vs.label}>
            分类 <span className="text-danger" aria-hidden="true">*</span>
            <span className="sr-only">（必选）</span>
          </label>
          {categories.length === 0 ? (
            <span className="text-xs text-ink-muted">当前学校暂无分类</span>
          ) : (
            <div
              className={
                variant === 'page'
                  ? 'grid grid-cols-3 sm:grid-cols-4 gap-2'
                  : 'grid grid-cols-3 gap-1.5'
              }
            >
              {categories.map((cat) => {
                const isActive = formData.category_id === cat.id;
                return (
                  <button
                    key={cat.id}
                    type="button"
                    onClick={() => handleCategorySelect(cat.id)}
                    aria-pressed={isActive}
                    className={`${vs.catChip} ${
                      isActive ? vs.catChipActive : vs.catChipInactive
                    } focus:outline-none focus-visible:ring-2 focus-visible:ring-lake focus-visible:ring-offset-2`}
                  >
                    <span className="text-sm" aria-hidden="true">{cat.icon || '📌'}</span>
                    <span className="truncate">{cat.name}</span>
                  </button>
                );
              })}
            </div>
          )}
          {selectedCategory?.description ? (
            <p className="text-[11px] text-ink-muted mt-1.5">{selectedCategory.description}</p>
          ) : null}
        </div>

        {/* 内容 */}
        <div>
          <label className={vs.label}>
            内容 <span className="text-danger">*</span>
          </label>
          <textarea
            name="content"
            value={formData.content}
            onChange={(e) => handleFieldChange('content', e.target.value)}
            placeholder="请输入内容（10-5000 字符）"
            rows={variant === 'page' ? 8 : 5}
            maxLength={5000}
            className={vs.textarea}
            required
          />
        </div>

        {/* 图片上传 + 预览（多图） */}
        <div>
          <label className={vs.label}>
            图片 <span className="text-ink-muted text-xs">（最多 {MAX_IMAGES} 张，每张 ≤ 5MB）</span>
          </label>
          <div className="flex flex-wrap gap-2">
            {formData.images.map((img) => (
              <div
                key={img.image_url}
                className="relative w-20 h-20 rounded-[10px] overflow-hidden border border-line bg-mist"
              >
                {/* 预览优先用缩略图：带宽友好 + 加载更快 */}
                <img
                  src={img.thumbnail_url || img.image_url}
                  alt="预览"
                  loading="lazy"
                  className="w-full h-full object-cover"
                />
                <button
                  type="button"
                  onClick={() => handleRemoveImage(img.image_url)}
                  className="absolute top-0.5 right-0.5 w-5 h-5 rounded-full bg-ink/60 text-white flex items-center justify-center hover:bg-ink/80"
                  aria-label="删除图片"
                >
                  <X size={12} />
                </button>
              </div>
            ))}
            {formData.images.length < MAX_IMAGES ? (
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={uploading}
                className="w-20 h-20 rounded-[10px] border border-dashed border-line hover:border-lake hover:bg-paper-hover flex flex-col items-center justify-center text-ink-muted transition-colors disabled:opacity-50"
                aria-label="上传图片"
              >
                {uploading ? (
                  <Loading size="sm" />
                ) : (
                  <>
                    <ImageIcon size={18} />
                    <span className="text-[10px] mt-1">添加图片</span>
                  </>
                )}
              </button>
            ) : null}
          </div>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/jpeg,image/png,image/gif"
            multiple
            onChange={handleImageChange}
            className="hidden"
          />
        </div>

        {/* 地点选择（本校校验） */}
        <div>
          <label className={vs.label} htmlFor="post-location-select">
            地点 <span className="text-ink-muted text-xs">（可选；不选则发布为无地点信息）</span>
          </label>
          <select
            id="post-location-select"
            value={formData.location_id ?? ''}
            onChange={(e) => handleLocationSelect(e.target.value)}
            className={vs.select}
          >
            <option value="">— 不选或选择已有地点 —</option>
            {verifiedLocations.length > 0 ? (
              <optgroup label="已核验地点">
                {verifiedLocations.map((loc) => (
                  <option key={loc.id} value={loc.id}>
                    {loc.name}
                  </option>
                ))}
              </optgroup>
            ) : null}
            {unverifiedLocations.length > 0 ? (
              <optgroup label="用户提交（待核验）">
                {unverifiedLocations.map((loc) => (
                  <option key={loc.id} value={loc.id}>
                    {loc.name}（待核验）
                  </option>
                ))}
              </optgroup>
            ) : null}
          </select>
        </div>

        {/* 信息截止时间（原"有效期"） */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Input
            label="信息截止时间"
            name="expire_at"
            type="datetime-local"
            value={formData.expire_at}
            onChange={(e) => handleFieldChange('expire_at', e.target.value)}
          />
          <Input
            label="联系方式"
            name="contact_info"
            type="text"
            value={formData.contact_info}
            onChange={(e) => handleFieldChange('contact_info', e.target.value)}
            placeholder="如微信/QQ/电话（可选）"
            maxLength={255}
          />
        </div>

        {/* 失物类型：仅当分类为 lost_found 时显示 */}
        {selectedCategory?.code === 'lost_found' ? (
          <div>
            <label className={vs.label} htmlFor="post-lost-type-select">
              失物类型 <span className="text-danger" aria-hidden="true">*</span>
              <span className="sr-only">（失物招领分类必选）</span>
            </label>
            <select
              id="post-lost-type-select"
              value={formData.lost_type}
              onChange={(e) =>
                handleFieldChange('lost_type', e.target.value as '' | 'lost' | 'found')
              }
              className={vs.select}
            >
              <option value="">— 请选择 —</option>
              <option value="lost">丢失</option>
              <option value="found">拾获</option>
            </select>
          </div>
        ) : null}

        {/* 匿名 */}
        <div>
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="is_anonymous"
              name="is_anonymous"
              checked={formData.is_anonymous}
              onChange={(e) => handleFieldChange('is_anonymous', e.target.checked)}
              disabled={!canAnonymous}
              className="w-4 h-4 text-lake border-line rounded focus:ring-lamp/40 disabled:cursor-not-allowed disabled:opacity-60"
            />
            <label
              htmlFor="is_anonymous"
              className={`text-sm text-ink ${canAnonymous ? 'cursor-pointer' : 'cursor-not-allowed opacity-80'}`}
            >
              匿名发布
            </label>
          </div>
          {!canAnonymous && (
            <p className="text-xs text-ink-muted mt-1 ml-6">
              当前学校已关闭匿名发布
            </p>
          )}
        </div>

        {/* 提示 */}
        <div className="bg-grass/8 text-[#476a51] rounded-[10px] px-4 py-3 text-xs leading-relaxed border border-grass/20">
          信息会过期，也能被更新。每条信息都有"最后确认时间"，路过时点一下仍然有效，就能帮后来的人少走弯路。
          <br />
          <span className="text-grass">提示：</span>可先"存为草稿"稍后再"提交审核"，审核通过后才会公开展示。
        </div>

        {/* 操作按钮 */}
        <div className={vs.submitRow}>
          <Button
            type="submit"
            variant="primary"
            size="md"
            loading={submitting}
            className={vs.draftFull ? 'w-full' : 'flex-1'}
            icon={!submitting && variant === 'panel' ? <Send size={15} /> : undefined}
          >
            {effectiveSubmitLabel}
          </Button>
          {showDraftButton ? (
            <Button
              type="button"
              variant="secondary"
              size="md"
              loading={submitting}
              onClick={(e) => handleSubmit(e as unknown as React.FormEvent, 'draft')}
              className={vs.draftFull ? 'w-full' : ''}
            >
              {effectiveDraftLabel}
            </Button>
          ) : null}
          {showCancelButton && onCancel ? (
            <Button type="button" variant="text" size="md" onClick={onCancel}>
              取消
            </Button>
          ) : null}
        </div>
      </form>
    </div>
  );
};

export default PostForm;

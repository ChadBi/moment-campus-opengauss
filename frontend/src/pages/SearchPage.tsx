import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { searchApi, type SearchSort, type SearchStatusFilter } from '../services/search';
import { categoriesApi, type CategoryListItem, type LocationListItem } from '../services/categories';
import type {
  AISearchIntent,
  AISearchOverrides,
  AISearchResponse,
  PostListItem,
} from '../types';
import { Avatar } from '../components/ui/Avatar';
import { Badge } from '../components/ui/Badge';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Loading } from '../components/ui/Loading';
import { MapPin, Clock, Search, Sparkles, SlidersHorizontal, X, ChevronDown, Map as MapIcon, AlertCircle, RefreshCw, Wand2, Lightbulb, History, Trash2 } from 'lucide-react';
import { useCampusStore } from '../store/useCampusStore';
import { useUIStore } from '../store/useUIStore';
import { formatRelativeTime as formatDate } from '../utils/date';

/**
 * DSC-01.1 + DSC-01.3 + AI-02.2 + UX-01.1: 搜索页
 *
 * 能力：
 *  - 多维度筛选：关键词 / 分类 / 地点 / 帖子类型 / 有效状态 / 时间范围 / 排序
 *  - 分页：基于后端 total/total_pages/has_more，支持"加载更多"
 *  - 错误提示：网络/服务端错误以可见 Toast + 内联错误卡片展示
 *  - 与地图联动：点击结果项可跳到地图并聚焦该帖子（?focus_post_id=xxx）
 *  - 三校隔离：依赖 Axios 拦截器自动注入 X-School-Code 头（TEN-03.2）
 *
 * AI-02.2 新增：
 *  - 模式切换：普通搜索 ↔ AI 结构化搜索（顶部 Chip 切换）
 *  - 搜索框提示语随模式变化
 *  - 可编辑筛选 Chip：AI 解析出的关键词/分类/排序/时间作为 Chip 展示，可点击编辑
 *  - "为什么匹配"：每条结果展开显示 match_reasons + score
 *  - 更新时间/地点/有效性：在结果项底部展示
 *  - 点击结果同步定位地图：handleOpenInMap 跳转 ?focus_post_id=xxx
 *  - AI 降级提示：fallback=true 时显示 banner，提示用户已切换为普通搜索
 *  - 不使用全屏聊天 UI
 *
 * UX-01.1 新增：
 *  - 最近搜索（localStorage，按学校 code 分键，最多 8 条，点击即搜）
 *  - 高频快捷问题（AI 模式下展示，点击直接发起 AI 搜索）
 *  - 普通筛选与 AI 搜索同一结果模型（已有 PostListItem）
 */

// UX-01.1: AI 模式高频快捷问题（通用自然语言示例，适用于任意校园场景）
const QUICK_QUESTIONS = [
  '最近有什么值得吐槽的事？',
  '有没有人一起组队自习或运动？',
  '有哪些二手物品在转让？',
  '最近有丢失或拾到物品吗？',
  '校园里有什么新鲜事？',
  '有哪些生活服务推荐？',
];

const SORT_OPTIONS: { value: SearchSort; label: string }[] = [
  { value: 'latest', label: '最新' },
  { value: 'hottest', label: '最热' },
  { value: 'active', label: '近期活动' },
  { value: 'nearest', label: '最近更新' },
];

const AI_SORT_OPTIONS: { value: string; label: string }[] = [
  ...SORT_OPTIONS,
  { value: 'relevance', label: '相关度' },
];

const STATUS_OPTIONS: { value: SearchStatusFilter; label: string }[] = [
  { value: 'valid', label: '全部可见' },
  { value: 'published', label: '仅已发布' },
  { value: 'expired', label: '仅已过期' },
];

const PAGE_SIZE = 10;

type SearchMode = 'normal' | 'ai';

// ============ UX-01.1: 最近搜索 localStorage 工具 ============
interface RecentSearchEntry {
  keyword: string;
  mode: SearchMode;
  searchedAt: string; // ISO
}

const MAX_RECENT = 8;

function recentStorageKey(schoolCode: string | null): string {
  return `moment_search_recent::${schoolCode ?? 'default'}`;
}

function loadRecent(schoolCode: string | null): RecentSearchEntry[] {
  try {
    const raw = localStorage.getItem(recentStorageKey(schoolCode));
    if (!raw) return [];
    const parsed = JSON.parse(raw) as RecentSearchEntry[];
    return Array.isArray(parsed) ? parsed.slice(0, MAX_RECENT) : [];
  } catch {
    return [];
  }
}

function saveRecent(schoolCode: string | null, entry: RecentSearchEntry): void {
  try {
    const list = loadRecent(schoolCode);
    // 同关键词 + 同模式去重（大小写不敏感）
    const filtered = list.filter(
      (it) =>
        !(it.keyword.toLowerCase() === entry.keyword.toLowerCase() && it.mode === entry.mode)
    );
    filtered.unshift(entry);
    localStorage.setItem(recentStorageKey(schoolCode), JSON.stringify(filtered.slice(0, MAX_RECENT)));
  } catch {
    // 隐私模式或配额不足：静默失败
  }
}

function removeRecent(schoolCode: string | null, keyword: string, mode: SearchMode): void {
  try {
    const list = loadRecent(schoolCode).filter(
      (it) => !(it.keyword === keyword && it.mode === mode)
    );
    localStorage.setItem(recentStorageKey(schoolCode), JSON.stringify(list));
  } catch {
    // 静默失败
  }
}

function clearRecent(schoolCode: string | null): void {
  try {
    localStorage.removeItem(recentStorageKey(schoolCode));
  } catch {
    // 静默失败
  }
}

function formatRecentTime(iso: string): string {
  try {
    const d = new Date(iso);
    const now = new Date();
    const diff = now.getTime() - d.getTime();
    if (diff < 60000) return '刚刚';
    const minutes = Math.floor(diff / 60000);
    if (minutes < 60) return `${minutes} 分钟前`;
    const hours = Math.floor(diff / 3600000);
    if (hours < 24) return `${hours} 小时前`;
    const days = Math.floor(diff / 86400000);
    return `${days} 天前`;
  } catch {
    return '';
  }
}

const SearchPage: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { showToast } = useUIStore();
  const currentSchoolId = useCampusStore((s) => s.currentSchoolId);
  const currentSchoolCode = useCampusStore((s) => s.currentSchoolCode);

  // ===== UX-01.1: 最近搜索（按学校 code 分键） =====
  const [recentState, setRecentState] = useState(() => ({
    schoolCode: currentSchoolCode,
    entries: loadRecent(currentSchoolCode),
  }));
  const recentSearches = recentState.schoolCode === currentSchoolCode
    ? recentState.entries
    : loadRecent(currentSchoolCode);
  const setRecentSearches = useCallback((entries: RecentSearchEntry[]) => {
    setRecentState({ schoolCode: currentSchoolCode, entries });
  }, [currentSchoolCode]);

  // ===== 模式切换状态（普通搜索 / AI 搜索）=====
  // 从 URL 读取初始模式：?mode=ai 切换到 AI 模式
  const [mode, setMode] = useState<SearchMode>(
    searchParams.get('mode') === 'ai' ? 'ai' : 'normal'
  );

  // ===== 筛选状态（普通搜索使用）=====
  // UX-01.1: 提前声明，便于下方 useCallback 引用（避免 TDZ）
  const [keyword, setKeyword] = useState(searchParams.get('keyword') ?? '');
  const [categorySelection, setCategorySelection] = useState<{ schoolId: number | null; id: number } | null>(() => {
    const id = searchParams.get('category_id');
    return id ? { schoolId: currentSchoolId, id: Number(id) } : null;
  });
  const [locationSelection, setLocationSelection] = useState<{ schoolId: number | null; id: number } | null>(() => {
    const id = searchParams.get('location_id');
    return id ? { schoolId: currentSchoolId, id: Number(id) } : null;
  });
  const categoryId = categorySelection?.schoolId === currentSchoolId ? categorySelection.id : null;
  const locationId = locationSelection?.schoolId === currentSchoolId ? locationSelection.id : null;
  const setCategoryId = (id: number | null) => {
    setCategorySelection(id === null ? null : { schoolId: currentSchoolId, id });
  };
  const setLocationId = (id: number | null) => {
    setLocationSelection(id === null ? null : { schoolId: currentSchoolId, id });
  };
  const [status, setStatus] = useState<SearchStatusFilter>(
    (searchParams.get('status') as SearchStatusFilter) || 'valid'
  );
  const [dateFrom, setDateFrom] = useState<string>(searchParams.get('date_from') ?? '');
  const [dateTo, setDateTo] = useState<string>(searchParams.get('date_to') ?? '');
  const [sort, setSort] = useState<SearchSort>(
    (searchParams.get('sort') as SearchSort) || 'latest'
  );

  // ===== AI 搜索状态 =====
  // AI 模式下的查询输入（独立于普通搜索的 keyword，便于切换模式时保留各自输入）
  const [aiQuery, setAiQuery] = useState(searchParams.get('ai_query') ?? '');
  // AI 解析出的意图（含 filters 与 reasons）
  const [aiIntent, setAiIntent] = useState<AISearchIntent | null>(null);
  // 用户编辑后的筛选覆盖项（提供时不再调用模型解析）
  const [aiOverrides, setAiOverrides] = useState<AISearchOverrides>({});
  // 用户是否已编辑过 Chip（用于区分首次解析与编辑后重搜）
  const [aiEdited, setAiEdited] = useState(false);
  // 每条结果的匹配理由
  const [aiMatchReasons, setAiMatchReasons] = useState<Record<number, string[]>>({});
  // 每条结果的确定性分数
  const [aiScores, setAiScores] = useState<Record<number, number>>({});
  // AI 是否已降级为普通搜索
  const [aiFallback, setAiFallback] = useState(false);
  const [aiFallbackReason, setAiFallbackReason] = useState<string | null>(null);
  // 展开匹配理由的 post_id 集合
  const [expandedReasons, setExpandedReasons] = useState<Set<number>>(new Set());

  // ===== UX-01.1: 记录最近搜索（在每次成功搜索后调用） =====
  const recordRecentSearch = useCallback(
    (kw: string, searchMode: SearchMode) => {
      const trimmed = kw.trim();
      if (!trimmed) return;
      const entry: RecentSearchEntry = {
        keyword: trimmed,
        mode: searchMode,
        searchedAt: new Date().toISOString(),
      };
      saveRecent(currentSchoolCode, entry);
      setRecentSearches(loadRecent(currentSchoolCode));
    },
    [currentSchoolCode, setRecentSearches]
  );

  // ===== UX-01.1: 移除单条最近搜索 =====
  const handleRemoveRecent = useCallback(
    (keyword: string, searchMode: SearchMode) => {
      removeRecent(currentSchoolCode, keyword, searchMode);
      setRecentSearches(loadRecent(currentSchoolCode));
    },
    [currentSchoolCode, setRecentSearches]
  );

  // ===== UX-01.1: 清空全部最近搜索 =====
  const handleClearAllRecent = useCallback(() => {
    clearRecent(currentSchoolCode);
    setRecentSearches([]);
  }, [currentSchoolCode, setRecentSearches]);

  // ===== UX-01.1: 点击最近搜索条目 → 立即搜索（依赖下方 doNormalSearchWithTag/doAiSearchWithTag，故用普通函数） =====
  const handleRecentClick = (entry: RecentSearchEntry) => {
    if (entry.mode === 'ai') {
      setMode('ai');
      setAiQuery(entry.keyword);
      void doAiSearchWithTag(entry.keyword);
    } else {
      setMode('normal');
      setKeyword(entry.keyword);
      void doNormalSearchWithTag(entry.keyword);
    }
  };

  // ===== UX-01.1: 快捷问题点击（AI 模式专用） =====
  const handleQuickQuestionClick = (question: string) => {
    setMode('ai');
    setAiQuery(question);
    void doAiSearchWithTag(question);
  };

  // ===== 数据状态 =====
  const [posts, setPosts] = useState<PostListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searched, setSearched] = useState(false);
  const [showFilters, setShowFilters] = useState(false);

  // ===== 筛选下拉数据（按当前学校过滤） =====
  const [categoryState, setCategoryState] = useState<{
    schoolId: number | null;
    items: CategoryListItem[];
    loading: boolean;
    error: boolean;
  }>({ schoolId: null, items: [], loading: true, error: false });
  const [locationState, setLocationState] = useState<{
    schoolId: number | null;
    items: LocationListItem[];
    loading: boolean;
    error: boolean;
  }>({ schoolId: null, items: [], loading: true, error: false });
  const [categoriesRetry, setCategoriesRetry] = useState(0);
  const [locationsRetry, setLocationsRetry] = useState(0);
  const categories = useMemo(
    () => categoryState.schoolId === currentSchoolId ? categoryState.items : [],
    [categoryState, currentSchoolId]
  );
  const locations = useMemo(
    () => locationState.schoolId === currentSchoolId ? locationState.items : [],
    [locationState, currentSchoolId]
  );
  const categoriesLoading = categoryState.schoolId !== currentSchoolId || categoryState.loading;
  const locationsLoading = locationState.schoolId !== currentSchoolId || locationState.loading;
  const categoriesError = categoryState.schoolId === currentSchoolId && categoryState.error;
  const locationsError = locationState.schoolId === currentSchoolId && locationState.error;

  // ===== 拉取筛选下拉数据 =====
  useEffect(() => {
    let cancelled = false;
    categoriesApi.listCategories()
      .then((items) => {
        if (!cancelled) {
          setCategoryState({ schoolId: currentSchoolId, items, loading: false, error: false });
        }
      })
      .catch(() => {
        if (!cancelled) {
          setCategoryState({ schoolId: currentSchoolId, items: [], loading: false, error: true });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [currentSchoolId, categoriesRetry]);

  useEffect(() => {
    let cancelled = false;
    categoriesApi.listLocations()
      .then((items) => {
        if (!cancelled) {
          setLocationState({ schoolId: currentSchoolId, items, loading: false, error: false });
        }
      })
      .catch(() => {
        if (!cancelled) {
          setLocationState({ schoolId: currentSchoolId, items: [], loading: false, error: true });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [currentSchoolId, locationsRetry]);

  // ===== 构造普通搜索请求参数 =====
  const buildParams = useCallback(
    (pageOverride: number) => {
      const params: Parameters<typeof searchApi.search>[0] = {
        page: pageOverride,
        page_size: PAGE_SIZE,
        sort,
        status,
      };
      const kw = keyword.trim();
      if (kw) params.keyword = kw;
      if (categoryId !== null) params.category_id = categoryId;
      if (locationId !== null) params.location_id = locationId;
      if (dateFrom) params.date_from = new Date(dateFrom).toISOString();
      if (dateTo) params.date_to = new Date(dateTo).toISOString();
      return params;
    },
    [keyword, categoryId, locationId, status, dateFrom, dateTo, sort]
  );

  // ===== 同步 URL 查询参数（深链接支持） =====
  const syncUrlParams = useCallback(() => {
    const next = new URLSearchParams();
    if (mode === 'ai') {
      next.set('mode', 'ai');
      const q = aiQuery.trim();
      if (q) next.set('ai_query', q);
    } else {
      const kw = keyword.trim();
      if (kw) next.set('keyword', kw);
      if (categoryId !== null) next.set('category_id', String(categoryId));
      if (locationId !== null) next.set('location_id', String(locationId));
      if (status !== 'valid') next.set('status', status);
      if (dateFrom) next.set('date_from', dateFrom);
      if (dateTo) next.set('date_to', dateTo);
      if (sort !== 'latest') next.set('sort', sort);
    }
    setSearchParams(next, { replace: true });
  }, [mode, aiQuery, keyword, categoryId, locationId, status, dateFrom, dateTo, sort, setSearchParams]);

  // ===== 普通搜索执行 =====
  const doNormalSearch = useCallback(
    async (pageOverride: number = 1, append: boolean = false) => {
      if (append) {
        setLoadingMore(true);
      } else {
        setLoading(true);
      }
      setError(null);
      try {
        const params = buildParams(pageOverride);
        const data = await searchApi.search(params);
        if (append) {
          setPosts((prev) => [...prev, ...data.items]);
        } else {
          setPosts(data.items);
        }
        setTotal(data.total);
        setTotalPages(data.total_pages);
        setHasMore(data.has_more);
        setPage(data.page);
        setSearched(true);
        // 普通搜索清空 AI 相关状态
        setAiIntent(null);
        setAiMatchReasons({});
        setAiScores({});
        setAiFallback(false);
        setAiFallbackReason(null);
        syncUrlParams();
        // UX-01.1: 首页（非"加载更多"）成功搜索且有关键词时记录到最近搜索
        if (!append) {
          const kw = keyword.trim();
          if (kw) recordRecentSearch(kw, 'normal');
        }
      } catch (err: unknown) {
        const e = err as { response?: { data?: { detail?: string } }; message?: string };
        const msg = e?.response?.data?.detail || e?.message || '搜索失败，请稍后重试';
        setError(msg);
        showToast(msg, 'error');
        if (!append) {
          setPosts([]);
          setTotal(0);
          setTotalPages(0);
          setHasMore(false);
        }
      } finally {
        setLoading(false);
        setLoadingMore(false);
      }
    },
    [buildParams, showToast, syncUrlParams, recordRecentSearch, keyword]
  );

  // ===== AI 搜索执行 =====
  const doAiSearch = useCallback(
    async (pageOverride: number = 1, append: boolean = false) => {
      const query = aiQuery.trim();
      if (!query) {
        showToast('请输入搜索内容', 'warning');
        return;
      }
      if (append) {
        setLoadingMore(true);
      } else {
        setLoading(true);
      }
      setError(null);
      try {
        const payload: Parameters<typeof searchApi.aiSearch>[0] = {
          query,
          page: pageOverride,
          page_size: PAGE_SIZE,
        };
        // 用户已编辑 Chip 时携带 overrides，后端不再调用模型解析
        if (aiEdited) {
          const cleaned = Object.fromEntries(
            Object.entries(aiOverrides).filter(
              ([, v]) => v !== undefined && v !== null && v !== ''
            )
          );
          if (Object.keys(cleaned).length > 0) {
            payload.overrides = cleaned as AISearchOverrides;
          }
        }
        const data: AISearchResponse = await searchApi.aiSearch(payload);
        if (append) {
          setPosts((prev) => [...prev, ...data.items]);
        } else {
          setPosts(data.items);
        }
        setTotal(data.total);
        setTotalPages(data.total_pages);
        setHasMore(data.has_more);
        setPage(data.page);
        setSearched(true);
        // 更新 AI 元数据
        setAiIntent(data.intent ?? null);
        setAiMatchReasons(data.match_reasons ?? {});
        setAiScores(data.scores ?? {});
        setAiFallback(data.fallback ?? false);
        setAiFallbackReason(data.fallback_reason ?? null);
        // 切换为普通搜索模式时不清空这些状态，但切回 AI 时由本次结果覆盖
        syncUrlParams();
        // UX-01.1: 首页（非"加载更多"）成功搜索记录到最近搜索
        if (!append) {
          recordRecentSearch(query, 'ai');
        }
      } catch (err: unknown) {
        const e = err as { response?: { data?: { detail?: string } }; message?: string };
        const msg = e?.response?.data?.detail || e?.message || 'AI 搜索失败，请稍后重试';
        setError(msg);
        showToast(msg, 'error');
        if (!append) {
          setPosts([]);
          setTotal(0);
          setTotalPages(0);
          setHasMore(false);
        }
      } finally {
        setLoading(false);
        setLoadingMore(false);
      }
    },
    [aiQuery, aiEdited, aiOverrides, showToast, syncUrlParams, recordRecentSearch]
  );

  // ===== 统一搜索入口（按模式分发） =====
  const doSearch = useCallback(
    async (pageOverride: number = 1, append: boolean = false) => {
      if (mode === 'ai') {
        return doAiSearch(pageOverride, append);
      }
      return doNormalSearch(pageOverride, append);
    },
    [mode, doAiSearch, doNormalSearch]
  );

  // ===== 首次加载：若 URL 含 keyword 或 ai_query 则自动触发搜索 =====
  useEffect(() => {
    if (mode === 'ai' && !searchParams.get('ai_query')) return;
    if (mode === 'normal' && !searchParams.get('keyword')) return;
    let cancelled = false;
    void Promise.resolve().then(() => {
      if (!cancelled) void doSearch(1, false);
    });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ===== 表单提交 =====
  const handleSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    // AI 模式下提交时重置编辑状态（视为新的查询）
    if (mode === 'ai') {
      setAiEdited(false);
      setAiOverrides({});
      setExpandedReasons(new Set());
    }
    void doSearch(1, false);
  };

  // ===== 重置筛选 =====
  const handleReset = () => {
    setKeyword('');
    setCategoryId(null);
    setLocationId(null);
    setStatus('valid');
    setDateFrom('');
    setDateTo('');
    setSort('latest');
    setAiQuery('');
    setAiIntent(null);
    setAiOverrides({});
    setAiEdited(false);
    setAiMatchReasons({});
    setAiScores({});
    setAiFallback(false);
    setAiFallbackReason(null);
    setExpandedReasons(new Set());
    setPosts([]);
    setTotal(0);
    setTotalPages(0);
    setHasMore(false);
    setSearched(false);
    setError(null);
    setSearchParams(new URLSearchParams(), { replace: true });
  };

  // ===== 加载更多 =====
  const handleLoadMore = () => {
    if (!hasMore || loadingMore) return;
    void doSearch(page + 1, true);
  };

  // ===== 跳转到地图并聚焦该帖子 =====
  const handleOpenInMap = (postId: number) => {
    navigate(`/map?focus_post_id=${postId}`);
  };

  // ===== 热门标签点击 =====
  const handleTagClick = (tag: string) => {
    if (mode === 'ai') {
      setAiQuery(tag);
      setAiEdited(false);
      setAiOverrides({});
      void doAiSearchWithTag(tag);
    } else {
      setKeyword(tag);
      void doNormalSearchWithTag(tag);
    }
  };

  const doNormalSearchWithTag = async (tag: string) => {
    setLoading(true);
    setError(null);
    try {
      const params = buildParams(1);
      params.keyword = tag;
      const data = await searchApi.search(params);
      setPosts(data.items);
      setTotal(data.total);
      setTotalPages(data.total_pages);
      setHasMore(data.has_more);
      setPage(data.page);
      setSearched(true);
      setAiIntent(null);
      setAiMatchReasons({});
      setAiScores({});
      setAiFallback(false);
      setAiFallbackReason(null);
      syncUrlParams();
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } }; message?: string };
      const msg = e?.response?.data?.detail || e?.message || '搜索失败，请稍后重试';
      setError(msg);
      showToast(msg, 'error');
      setPosts([]);
    } finally {
      setLoading(false);
    }
  };

  const doAiSearchWithTag = async (tag: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await searchApi.aiSearch({ query: tag, page: 1, page_size: PAGE_SIZE });
      setPosts(data.items);
      setTotal(data.total);
      setTotalPages(data.total_pages);
      setHasMore(data.has_more);
      setPage(data.page);
      setSearched(true);
      setAiIntent(data.intent ?? null);
      setAiMatchReasons(data.match_reasons ?? {});
      setAiScores(data.scores ?? {});
      setAiFallback(data.fallback ?? false);
      setAiFallbackReason(data.fallback_reason ?? null);
      syncUrlParams();
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } }; message?: string };
      const msg = e?.response?.data?.detail || e?.message || 'AI 搜索失败，请稍后重试';
      setError(msg);
      showToast(msg, 'error');
      setPosts([]);
    } finally {
      setLoading(false);
    }
  };

  // ===== 切换模式 =====
  const handleModeChange = (nextMode: SearchMode) => {
    if (nextMode === mode) return;
    setMode(nextMode);
    // 切换模式时清空结果与 AI 状态，保留各自输入
    setPosts([]);
    setTotal(0);
    setTotalPages(0);
    setHasMore(false);
    setSearched(false);
    setError(null);
    setAiIntent(null);
    setAiMatchReasons({});
    setAiScores({});
    setAiFallback(false);
    setAiFallbackReason(null);
    setAiEdited(false);
    setAiOverrides({});
    setExpandedReasons(new Set());
    // 同步 URL（避免旧参数残留）
    const next = new URLSearchParams();
    if (nextMode === 'ai') {
      next.set('mode', 'ai');
      const q = aiQuery.trim();
      if (q) next.set('ai_query', q);
    } else {
      const kw = keyword.trim();
      if (kw) next.set('keyword', kw);
    }
    setSearchParams(next, { replace: true });
  };

  // ===== AI Chip 编辑：更新 overrides 并重新搜索 =====
  const updateAiOverride = (patch: Partial<AISearchOverrides>) => {
    const nextOverrides = { ...aiOverrides, ...patch };
    setAiOverrides(nextOverrides);
    setAiEdited(true);
    // 立即触发重新搜索（携带 overrides）
    void doAiSearchWithOverrides(nextOverrides);
  };

  const doAiSearchWithOverrides = async (overrides: AISearchOverrides) => {
    const query = aiQuery.trim();
    if (!query) return;
    setLoading(true);
    setError(null);
    try {
      const cleaned = Object.fromEntries(
        Object.entries(overrides).filter(
          ([, v]) => v !== undefined && v !== null && v !== ''
        )
      );
      const payload: Parameters<typeof searchApi.aiSearch>[0] = {
        query,
        page: 1,
        page_size: PAGE_SIZE,
      };
      if (Object.keys(cleaned).length > 0) {
        payload.overrides = cleaned as AISearchOverrides;
      }
      const data = await searchApi.aiSearch(payload);
      setPosts(data.items);
      setTotal(data.total);
      setTotalPages(data.total_pages);
      setHasMore(data.has_more);
      setPage(data.page);
      setSearched(true);
      // 保留 intent（overrides 模式下后端可能仍返回原 intent 或 None）
      if (data.intent) setAiIntent(data.intent);
      setAiMatchReasons(data.match_reasons ?? {});
      setAiScores(data.scores ?? {});
      setAiFallback(data.fallback ?? false);
      setAiFallbackReason(data.fallback_reason ?? null);
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } }; message?: string };
      const msg = e?.response?.data?.detail || e?.message || 'AI 搜索失败，请稍后重试';
      setError(msg);
      showToast(msg, 'error');
      setPosts([]);
    } finally {
      setLoading(false);
    }
  };

  // ===== 展开/折叠匹配理由 =====
  const toggleReasons = (postId: number) => {
    setExpandedReasons((prev) => {
      const next = new Set(prev);
      if (next.has(postId)) {
        next.delete(postId);
      } else {
        next.add(postId);
      }
      return next;
    });
  };

  // ===== 当前激活筛选数量（用于"筛选"按钮角标，普通模式） =====
  const activeFilterCount = useMemo(() => {
    let n = 0;
    if (categoryId !== null) n++;
    if (locationId !== null) n++;
    if (status !== 'valid') n++;
    if (dateFrom) n++;
    if (dateTo) n++;
    if (sort !== 'latest') n++;
    return n;
  }, [categoryId, locationId, status, dateFrom, dateTo, sort]);

  const hotTags = useMemo(() => {
    return categories
      .slice()
      .sort((a, b) => a.sort_order - b.sort_order)
      .slice(0, 8)
      .map((c) => c.name);
  }, [categories]);

  // ===== 格式化有效性（expire_at） =====
  const formatValidity = (expireAt?: string) => {
    if (!expireAt) return null;
    const expire = new Date(expireAt);
    const now = new Date();
    if (expire.getTime() <= now.getTime()) {
      return { text: '已过期', className: 'text-ink-muted' };
    }
    const diff = expire.getTime() - now.getTime();
    const days = Math.floor(diff / 86400000);
    const hours = Math.floor((diff % 86400000) / 3600000);
    if (days > 0) return { text: `${days}天后过期`, className: 'text-success' };
    if (hours > 0) return { text: `${hours}小时后过期`, className: 'text-lamp' };
    return { text: '即将过期', className: 'text-danger' };
  };

  // ===== AI 模式下当前生效的筛选 Chip 数据 =====
  const aiActiveFilters = useMemo(() => {
    if (!aiIntent) return null;
    const f = aiIntent.filters;
    // 优先使用 overrides（用户编辑后的值），其次使用 AI 解析的值
    const keywordValue = aiEdited ? aiOverrides.keyword ?? f.keyword : f.keyword;
    const categoryValue = aiEdited ? aiOverrides.category_id ?? f.category_id : f.category_id;
    const sortValue = aiEdited ? aiOverrides.sort ?? f.sort : f.sort;
    const dateFromValue = aiEdited
      ? aiOverrides.date_from
        ? new Date(aiOverrides.date_from).toISOString()
        : f.date_from
      : f.date_from;
    const dateToValue = aiEdited
      ? aiOverrides.date_to
        ? new Date(aiOverrides.date_to).toISOString()
        : f.date_to
      : f.date_to;
    return {
      keyword: keywordValue,
      category_id: categoryValue,
      category_name: f.category_name,
      sort: sortValue,
      date_from: dateFromValue,
      date_to: dateToValue,
    };
  }, [aiIntent, aiEdited, aiOverrides]);

  return (
    <div className="max-w-2xl mx-auto py-4">
      <header className="mb-5 px-1">
        <h1 className="font-display font-bold text-[24px] tracking-wide text-lake leading-tight">搜索</h1>
        <p className="text-ink-muted text-sm mt-1">发现校园生活的每一刻</p>
      </header>

      {/* 模式切换 */}
      <div className="mb-3 flex items-center gap-1.5">
        <button
          type="button"
          onClick={() => handleModeChange('normal')}
          className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all ${
            mode === 'normal'
              ? 'bg-lake text-white shadow-lake'
              : 'bg-mist text-ink-sub hover:bg-line'
          }`}
        >
          <Search size={12} />
          普通搜索
        </button>
        <button
          type="button"
          onClick={() => handleModeChange('ai')}
          className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all ${
            mode === 'ai'
              ? 'bg-lake text-white shadow-lake'
              : 'bg-mist text-ink-sub hover:bg-line'
          }`}
        >
          <Wand2 size={12} />
          AI 智能搜索
        </button>
      </div>

      {/* 搜索框 */}
      <form onSubmit={handleSubmit} className="mb-3" role="search" aria-label={mode === 'ai' ? 'AI 智能搜索' : '校园信息搜索'}>
        <div className="relative">
          <Input
            value={mode === 'ai' ? aiQuery : keyword}
            onChange={(e) =>
              mode === 'ai' ? setAiQuery(e.target.value) : setKeyword(e.target.value)
            }
            placeholder={
              mode === 'ai'
                ? '试试问"最近图书馆有什么活动"或"找一张校园卡"...'
                : '搜索标题、内容、地点...'
            }
            icon={mode === 'ai' ? <Sparkles size={16} /> : <Search size={16} />}
            className="pr-32"
            aria-label={mode === 'ai' ? 'AI 搜索问题' : '搜索关键词'}
            autoComplete="off"
            spellCheck={mode === 'ai'}
          />
          <div className="absolute right-1 top-1/2 -translate-y-1/2 flex items-center gap-1">
            {mode === 'normal' && (
              <button
                type="button"
                onClick={() => setShowFilters((v) => !v)}
                className={`relative w-9 h-9 flex items-center justify-center rounded-md transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-lake focus-visible:ring-offset-2 ${
                  showFilters || activeFilterCount > 0
                    ? 'bg-lake/10 text-lake'
                    : 'text-ink-sub hover:bg-mist'
                }`}
                aria-label={`筛选${activeFilterCount > 0 ? `（已应用 ${activeFilterCount} 个）` : ''}`}
                aria-expanded={showFilters}
              >
                <SlidersHorizontal size={16} aria-hidden="true" />
                {activeFilterCount > 0 && (
                  <span
                    className="absolute -top-1 -right-1 bg-lamp text-white text-[10px] leading-none rounded-full w-4 h-4 flex items-center justify-center font-bold"
                    aria-hidden="true"
                  >
                    {activeFilterCount}
                  </span>
                )}
              </button>
            )}
            <Button
              type="submit"
              variant="primary"
              size="sm"
              disabled={loading}
            >
              {mode === 'ai' ? 'AI 搜索' : '搜索'}
            </Button>
          </div>
        </div>
      </form>

      {/* 筛选面板（仅普通模式） */}
      {mode === 'normal' && showFilters && (
        <div className="bg-paper rounded-[16px] border border-line/60 p-4 shadow-sm mb-3">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <SlidersHorizontal size={14} className="text-lake" />
              <span className="text-sm font-semibold text-ink">筛选条件</span>
              {activeFilterCount > 0 && (
                <span className="text-xs text-ink-muted">（{activeFilterCount} 项已选）</span>
              )}
            </div>
            <button
              type="button"
              onClick={handleReset}
              className="text-xs text-ink-muted hover:text-danger flex items-center gap-1"
            >
              <X size={12} />
              清空
            </button>
          </div>

          <div className="grid grid-cols-2 gap-3 mb-3">
            {/* 分类 */}
            <div>
              <label className="block text-xs font-medium text-ink-sub mb-1">分类</label>
              <div className="relative">
                <select
                  value={categoryId ?? ''}
                  onChange={(e) => setCategoryId(e.target.value ? Number(e.target.value) : null)}
                  disabled={categoriesLoading || categoriesError}
                  className="w-full appearance-none px-3 py-2 pr-8 bg-white/78 border border-line rounded-md text-sm text-ink focus:outline-none focus:border-lake transition-all"
                >
                  <option value="">{categoriesLoading ? '分类加载中...' : categoriesError ? '分类加载失败' : '全部分类'}</option>
                  {categories.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.icon} {c.name}
                    </option>
                  ))}
                </select>
                <ChevronDown size={14} className="absolute right-2 top-1/2 -translate-y-1/2 text-ink-muted pointer-events-none" />
              </div>
              {categoriesError && (
                <button type="button" onClick={() => {
                  setCategoryState({ schoolId: currentSchoolId, items: [], loading: true, error: false });
                  setCategoriesRetry((value) => value + 1);
                }} className="mt-1 inline-flex items-center gap-1 text-xs text-danger">
                  <RefreshCw size={11} />
                  重试分类
                </button>
              )}
            </div>

            {/* 地点 */}
            <div>
              <label className="block text-xs font-medium text-ink-sub mb-1">地点</label>
              <div className="relative">
                <select
                  value={locationId ?? ''}
                  onChange={(e) => setLocationId(e.target.value ? Number(e.target.value) : null)}
                  disabled={locationsLoading || locationsError}
                  className="w-full appearance-none px-3 py-2 pr-8 bg-white/78 border border-line rounded-md text-sm text-ink focus:outline-none focus:border-lake transition-all"
                >
                  <option value="">{locationsLoading ? '地点加载中...' : locationsError ? '地点加载失败' : '全部地点'}</option>
                  {locations.map((l) => (
                    <option key={l.id} value={l.id}>
                      {l.name}{l.is_verified ? '' : '（未核验）'}
                    </option>
                  ))}
                </select>
                <ChevronDown size={14} className="absolute right-2 top-1/2 -translate-y-1/2 text-ink-muted pointer-events-none" />
              </div>
              {locationsError && (
                <button type="button" onClick={() => {
                  setLocationState({ schoolId: currentSchoolId, items: [], loading: true, error: false });
                  setLocationsRetry((value) => value + 1);
                }} className="mt-1 inline-flex items-center gap-1 text-xs text-danger">
                  <RefreshCw size={11} />
                  重试地点
                </button>
              )}
            </div>

            {/* 状态 */}
            <div>
              <label className="block text-xs font-medium text-ink-sub mb-1">有效状态</label>
              <div className="relative">
                <select
                  value={status}
                  onChange={(e) => setStatus(e.target.value as SearchStatusFilter)}
                  className="w-full appearance-none px-3 py-2 pr-8 bg-white/78 border border-line rounded-md text-sm text-ink focus:outline-none focus:border-lake transition-all"
                >
                  {STATUS_OPTIONS.map((s) => (
                    <option key={s.value} value={s.value}>
                      {s.label}
                    </option>
                  ))}
                </select>
                <ChevronDown size={14} className="absolute right-2 top-1/2 -translate-y-1/2 text-ink-muted pointer-events-none" />
              </div>
            </div>

            {/* 起始时间 */}
            <div>
              <label className="block text-xs font-medium text-ink-sub mb-1">起始时间</label>
              <input
                type="date"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
                className="w-full px-3 py-2 bg-white/78 border border-line rounded-md text-sm text-ink focus:outline-none focus:border-lake transition-all"
              />
            </div>

            {/* 截止时间 */}
            <div>
              <label className="block text-xs font-medium text-ink-sub mb-1">截止时间</label>
              <input
                type="date"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
                className="w-full px-3 py-2 bg-white/78 border border-line rounded-md text-sm text-ink focus:outline-none focus:border-lake transition-all"
              />
            </div>
          </div>

          {/* 排序 Chip 行 */}
          <div>
            <label className="block text-xs font-medium text-ink-sub mb-1.5">排序</label>
            <div className="flex flex-wrap gap-1.5">
              {SORT_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => setSort(opt.value)}
                  className={`px-3 py-1.5 rounded-full text-xs font-medium transition-all ${
                    sort === opt.value
                      ? 'bg-lake text-white shadow-lake'
                      : 'bg-mist text-ink-sub hover:bg-line'
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          <div className="flex gap-2 mt-4">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={handleReset}
              className="flex-1"
            >
              重置
            </Button>
            <Button
              type="button"
              variant="primary"
              size="sm"
              onClick={() => {
                setShowFilters(false);
                void doSearch(1, false);
              }}
              className="flex-1"
            >
              应用筛选
            </Button>
          </div>
        </div>
      )}

      {/* AI 意图与可编辑筛选 Chip（仅 AI 模式 + 有意图时） */}
      {mode === 'ai' && aiIntent && (
        <div className="bg-paper rounded-[16px] border border-line/60 p-4 shadow-sm mb-3">
          <div className="flex items-start gap-2 mb-3">
            <Lightbulb size={14} className="text-lamp mt-0.5 flex-shrink-0" />
            <div className="flex-1">
              <div className="text-xs font-semibold text-ink mb-0.5">AI 意图</div>
              <div className="text-xs text-ink-sub leading-relaxed">{aiIntent.intent}</div>
            </div>
          </div>

          {/* 可编辑筛选 Chip */}
          <div className="flex flex-wrap gap-1.5 mb-2">
            {/* 关键词 Chip */}
            {aiActiveFilters?.keyword && (
              <div className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-lake/10 text-lake text-xs font-medium">
                <span className="opacity-70">关键词:</span>
                <input
                  type="text"
                  value={aiOverrides.keyword ?? aiActiveFilters.keyword ?? ''}
                  onChange={(e) => {
                    // 即时更新本地状态，但只在 blur 或 enter 时触发搜索
                    setAiOverrides((prev) => ({ ...prev, keyword: e.target.value }));
                    setAiEdited(true);
                  }}
                  onBlur={(e) => {
                    if (e.target.value !== (aiActiveFilters.keyword ?? '')) {
                      void doAiSearchWithOverrides({ ...aiOverrides, keyword: e.target.value });
                    }
                  }}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      (e.target as HTMLInputElement).blur();
                    }
                  }}
                  className="bg-transparent border-none outline-none w-20 text-lake placeholder-lake/50"
                  placeholder="关键词"
                />
                <button
                  type="button"
                  onClick={() => updateAiOverride({ keyword: '' })}
                  className="hover:bg-lake/20 rounded-full p-0.5"
                  aria-label="移除关键词"
                >
                  <X size={10} />
                </button>
              </div>
            )}

            {/* 分类 Chip */}
            {aiActiveFilters?.category_id && (
              <div className="inline-flex items-center gap-1 relative">
                <select
                  value={aiActiveFilters.category_id}
                  onChange={(e) => updateAiOverride({ category_id: e.target.value ? Number(e.target.value) : undefined })}
                  disabled={categoriesLoading || categoriesError}
                  className="appearance-none pl-2.5 pr-6 py-1 rounded-full bg-lake/10 text-lake text-xs font-medium border-none outline-none cursor-pointer"
                >
                  {categories.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.icon} {c.name}
                    </option>
                  ))}
                </select>
                <ChevronDown size={10} className="absolute right-1.5 top-1/2 -translate-y-1/2 text-lake pointer-events-none" />
                <button
                  type="button"
                  onClick={() => updateAiOverride({ category_id: undefined })}
                  className="ml-0.5 hover:bg-lake/20 rounded-full p-0.5 text-lake"
                  aria-label="移除分类"
                >
                  <X size={10} />
                </button>
              </div>
            )}

            {/* 排序 Chip */}
            {aiActiveFilters?.sort && (
              <div className="inline-flex items-center gap-1 relative">
                <select
                  value={aiActiveFilters.sort}
                  onChange={(e) => updateAiOverride({ sort: e.target.value as AISearchOverrides['sort'] })}
                  className="appearance-none pl-2.5 pr-6 py-1 rounded-full bg-lake/10 text-lake text-xs font-medium border-none outline-none cursor-pointer"
                >
                  {AI_SORT_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
                <ChevronDown size={10} className="absolute right-1.5 top-1/2 -translate-y-1/2 text-lake pointer-events-none" />
              </div>
            )}

            {/* 时间范围 Chip */}
            {(aiActiveFilters?.date_from || aiActiveFilters?.date_to) && (
              <div className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-lake/10 text-lake text-xs font-medium">
                <Clock size={10} />
                <input
                  type="date"
                  value={
                    aiOverrides.date_from
                      ? aiOverrides.date_from.split('T')[0]
                      : aiActiveFilters.date_from
                      ? new Date(aiActiveFilters.date_from).toISOString().split('T')[0]
                      : ''
                  }
                  onChange={(e) => updateAiOverride({ date_from: e.target.value || undefined })}
                  className="bg-transparent border-none outline-none text-lake text-xs"
                />
                <span className="opacity-50">~</span>
                <input
                  type="date"
                  value={
                    aiOverrides.date_to
                      ? aiOverrides.date_to.split('T')[0]
                      : aiActiveFilters.date_to
                      ? new Date(aiActiveFilters.date_to).toISOString().split('T')[0]
                      : ''
                  }
                  onChange={(e) => updateAiOverride({ date_to: e.target.value || undefined })}
                  className="bg-transparent border-none outline-none text-lake text-xs"
                />
              </div>
            )}
          </div>

          {/* 整体匹配理由 */}
          {aiIntent.reasons && aiIntent.reasons.length > 0 && (
            <div className="mt-2 pt-2 border-t border-line/40">
              <div className="text-[11px] text-ink-muted leading-relaxed">
                <span className="font-medium">整体理由：</span>
                {aiIntent.reasons.join('；')}
              </div>
            </div>
          )}
        </div>
      )}

      {/* AI 降级提示（仅 AI 模式 + fallback=true） */}
      {mode === 'ai' && aiFallback && (
        <div className="bg-lamp/10 border border-lamp/30 rounded-[16px] p-4 mb-4 flex items-start gap-3">
          <AlertCircle size={18} className="text-lamp flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <h3 className="font-semibold text-lamp mb-0.5 text-sm">已切换为普通搜索</h3>
            <p className="text-xs text-ink-sub mb-2">
              {aiFallbackReason || 'AI 解析暂时不可用，已自动降级为普通搜索以保证结果可用。'}
            </p>
            <button
              type="button"
              onClick={() => handleModeChange('normal')}
              className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-lamp text-white text-xs font-medium hover:bg-lamp/90 transition-colors"
            >
              <Search size={11} />
              切换到普通搜索
            </button>
          </div>
        </div>
      )}

      {/* UX-01.1: 最近搜索 / 快捷问题 / 热门搜索（仅未搜索时展示） */}
      {!searched && !loading && (
        <>
          {/* 最近搜索（按学校 code 分键，最多 8 条） */}
          {recentSearches.length > 0 && (
            <div className="bg-paper rounded-[16px] border border-line/60 p-5 shadow-sm mb-3">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <History size={16} className="text-lake" />
                  <span className="text-sm font-semibold text-ink">最近搜索</span>
                </div>
                <button
                  type="button"
                  onClick={handleClearAllRecent}
                  className="text-xs text-ink-muted hover:text-danger flex items-center gap-1"
                  aria-label="清空全部最近搜索"
                >
                  <Trash2 size={11} />
                  清空
                </button>
              </div>
              <div className="space-y-1">
                {recentSearches.map((entry, idx) => (
                  <div
                    key={`${entry.keyword}-${entry.mode}-${idx}`}
                    className="flex items-center gap-2 px-2 py-1.5 rounded-[8px] hover:bg-paper-hover transition-colors group"
                  >
                    <button
                      type="button"
                      onClick={() => handleRecentClick(entry)}
                      className="flex-1 flex items-center gap-2 text-left min-w-0"
                      aria-label={`搜索 ${entry.keyword}`}
                    >
                      <Clock size={12} className="text-ink-muted flex-shrink-0" />
                      <span className="text-sm text-ink truncate flex-1">{entry.keyword}</span>
                      <span className="text-[10px] text-ink-muted flex-shrink-0">
                        {entry.mode === 'ai' ? 'AI' : '普通'} · {formatRecentTime(entry.searchedAt)}
                      </span>
                    </button>
                    <button
                      type="button"
                      onClick={() => handleRemoveRecent(entry.keyword, entry.mode)}
                      className="opacity-0 group-hover:opacity-100 text-ink-muted hover:text-danger p-1 rounded transition-all"
                      aria-label={`移除 ${entry.keyword}`}
                    >
                      <X size={12} />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* UX-01.1: AI 模式快捷问题 */}
          {mode === 'ai' && (
            <div className="bg-paper rounded-[16px] border border-line/60 p-5 shadow-sm mb-3">
              <div className="flex items-center gap-2 mb-3">
                <Lightbulb size={16} className="text-lamp" />
                <span className="text-sm font-semibold text-ink">高频快捷问题</span>
              </div>
              <div className="flex flex-col gap-1.5">
                {QUICK_QUESTIONS.map((q) => (
                  <button
                    key={q}
                    type="button"
                    onClick={() => handleQuickQuestionClick(q)}
                    className="flex items-center gap-2 px-3 py-2 rounded-[10px] text-sm text-ink-sub bg-mist hover:bg-lake/10 hover:text-lake transition-colors text-left"
                  >
                    <Sparkles size={12} className="text-lamp flex-shrink-0" />
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}

          {(hotTags.length > 0 || categoriesLoading || categoriesError) && (
            <div className="bg-paper rounded-[16px] border border-line/60 p-5 shadow-sm mb-4">
              <div className="flex items-center gap-2 mb-3">
                <Sparkles size={16} className="text-lamp" />
                <span className="text-sm font-semibold text-ink">热门搜索</span>
              </div>
              {categoriesLoading ? (
                <Loading size="sm" text="分类加载中..." />
              ) : categoriesError ? (
                <button type="button" onClick={() => {
                  setCategoryState({ schoolId: currentSchoolId, items: [], loading: true, error: false });
                  setCategoriesRetry((value) => value + 1);
                }} className="inline-flex items-center gap-1.5 text-sm text-danger">
                  <RefreshCw size={13} />
                  分类加载失败，点击重试
                </button>
              ) : (
                <div className="flex flex-wrap gap-2">
                  {hotTags.map((tag) => (
                    <button
                      key={tag}
                      type="button"
                      onClick={() => handleTagClick(tag)}
                      className="inline-flex items-center px-2.5 py-1 rounded-[6px] text-xs font-medium bg-mist text-ink-sub hover:bg-lake/10 hover:text-lake transition-colors"
                    >
                      {tag}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
        </>
      )}

      {/* 错误提示 */}
      {error && !loading && (
        <div className="bg-danger/10 border border-danger/30 rounded-[16px] p-5 mb-4 flex items-start gap-3">
          <AlertCircle size={20} className="text-danger flex-shrink-0 mt-0.5" />
          <div className="flex-1">
            <h3 className="font-semibold text-danger mb-1">搜索失败</h3>
            <p className="text-sm text-ink-sub mb-3">{error}</p>
            <button
              type="button"
              onClick={() => void doSearch(1, false)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-danger text-white text-xs font-medium hover:bg-danger/90 transition-colors"
            >
              <RefreshCw size={12} />
              重试
            </button>
          </div>
        </div>
      )}

      {/* 加载中 */}
      {loading && (
        <div className="py-12">
          <Loading text={mode === 'ai' ? 'AI 搜索中...' : '搜索中...'} />
        </div>
      )}

      {/* 初始空状态 */}
      {!loading && !searched && !error && (
        <div className="bg-paper rounded-[16px] border border-line/60 p-10 text-center">
          <div className="text-[48px] leading-none mb-4">🔎</div>
          <h3 className="text-lg font-display font-bold text-ink mb-2">
            {mode === 'ai' ? 'AI 智能搜索' : '搜索校园信息'}
          </h3>
          <p className="text-ink-sub text-sm">
            {mode === 'ai'
              ? '用自然语言描述你的需求，AI 帮你精准匹配'
              : '输入关键词，或点击上方热门标签开始探索'}
          </p>
        </div>
      )}

      {/* 空结果 */}
      {!loading && searched && posts.length === 0 && !error && (
        <div
          className="bg-paper rounded-[16px] border border-line/60 p-10 text-center"
          role="status"
          aria-live="polite"
        >
          <div className="text-[48px] leading-none mb-4" aria-hidden="true">🗂️</div>
          <h3 className="text-lg font-display font-bold text-ink mb-2">未找到相关内容</h3>
          <p className="text-ink-sub text-sm mb-4">
            {mode === 'ai' ? '尝试换一种描述方式' : '换一个关键词试试，或调整筛选条件'}
          </p>
          <Button variant="secondary" size="sm" onClick={handleReset}>
            清空筛选
          </Button>
        </div>
      )}

      {/* 搜索结果 */}
      {!loading && posts.length > 0 && (
        <>
          {/* UX-01.7: aria-live="polite" 让屏幕阅读器播报结果数量 */}
          <div
            className="mb-3 text-sm text-ink-sub flex items-center justify-between"
            aria-live="polite"
            aria-atomic="true"
          >
            <span className="text-xs bg-lake/10 text-lake px-2 py-0.5 rounded-[6px]">
              共 {total} 条结果
              {totalPages > 1 && ` · 第 ${page}/${totalPages} 页`}
              {mode === 'ai' && aiIntent && !aiFallback && (
                <span className="ml-1.5 opacity-70">· AI 排序</span>
              )}
            </span>
            <button
              type="button"
              onClick={() => navigate('/map')}
              className="text-xs text-ink-muted hover:text-lake flex items-center gap-1 focus:outline-none focus-visible:ring-2 focus-visible:ring-lake focus-visible:ring-offset-2 focus-visible:rounded-[6px]"
            >
              <MapIcon size={12} aria-hidden="true" />
              切换到地图
            </button>
          </div>

          <div className="space-y-0">
            {posts.map((post) => {
              const reasons = aiMatchReasons[post.id] || [];
              const score = aiScores[post.id];
              const isExpanded = expandedReasons.has(post.id);
              const validity = formatValidity(post.expire_at);
              return (
                <article
                  key={post.id}
                  className="bg-paper border border-line/60 rounded-[16px] shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-all duration-200 cursor-pointer mb-3 overflow-hidden"
                  onClick={() => navigate(`/posts/${post.id}`)}
                >
                  <div className="px-5 pt-4 pb-3">
                    <div className="flex items-center gap-2 mb-2">
                      <Avatar
                        src={post.author?.avatar_url}
                        fallback={post.author?.nickname?.[0] || '?'}
                        size="sm"
                      />
                      <span className="font-medium text-ink text-sm">
                        {post.author?.nickname || '匿名用户'}
                      </span>
                      <Badge>
                        {post.category?.name || '未分类'}
                      </Badge>
                      {post.status === 'expired' && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-ink-muted/20 text-ink-muted">
                          已过期
                        </span>
                      )}
                      <span className="text-xs text-ink-muted ml-auto flex items-center gap-1">
                        <Clock size={11} />
                        {formatDate(post.created_at)}
                      </span>
                    </div>
                    <h3 className="font-semibold text-[15px] text-ink mb-1.5 line-clamp-2 leading-[1.5]">
                      {post.title}
                    </h3>
                    <p className="text-ink-sub text-[14px] line-clamp-2 leading-[1.7]">
                      {post.content}
                    </p>

                    {/* AI 匹配理由（仅 AI 模式且有理由时展示） */}
                    {mode === 'ai' && reasons.length > 0 && (
                      <div className="mt-2.5 pt-2 border-t border-line/40">
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            toggleReasons(post.id);
                          }}
                          className="inline-flex items-center gap-1 text-xs text-lake hover:bg-lake/10 px-1.5 py-0.5 rounded transition-colors"
                        >
                          <Lightbulb size={11} />
                          {isExpanded ? '收起理由' : '为什么匹配？'}
                          {typeof score === 'number' && (
                            <span className="ml-1 text-[10px] text-ink-muted">
                              (分数 {score.toFixed(2)})
                            </span>
                          )}
                        </button>
                        {isExpanded && (
                          <ul className="mt-1.5 space-y-1">
                            {reasons.map((r, idx) => (
                              <li
                                key={idx}
                                className="text-[11px] text-ink-sub leading-relaxed flex items-start gap-1.5"
                              >
                                <span className="text-lamp mt-0.5">•</span>
                                <span>{r}</span>
                              </li>
                            ))}
                          </ul>
                        )}
                      </div>
                    )}
                  </div>
                  <div className="px-5 py-2.5 border-t border-ink-divider/60 flex items-center justify-between text-xs text-ink-muted">
                    <span className="flex items-center gap-1">
                      <MapPin size={11} />
                      {post.location?.name || '未知地点'}
                    </span>
                    <div className="flex items-center gap-2">
                      {/* 有效性展示 */}
                      {validity && (
                        <span className={`flex items-center gap-0.5 ${validity.className}`}>
                          <Clock size={10} />
                          {validity.text}
                        </span>
                      )}
                      {/* 更新时间（PostListResponse 未返回 updated_at，使用 created_at 作为发布时间） */}
                      <span className="flex items-center gap-0.5">
                        <RefreshCw size={10} />
                        {formatDate(post.created_at)}
                      </span>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleOpenInMap(post.id);
                        }}
                        className="flex items-center gap-1 px-2 py-1 rounded text-lake hover:bg-lake/10 transition-colors"
                        aria-label="在地图查看"
                      >
                        <MapIcon size={11} />
                        地图
                      </button>
                    </div>
                  </div>
                </article>
              );
            })}
          </div>

          {/* 加载更多 / 分页 */}
          {hasMore && (
            <div className="flex justify-center mt-4 mb-4">
              <Button
                type="button"
                variant="secondary"
                size="md"
                onClick={handleLoadMore}
                disabled={loadingMore}
              >
                {loadingMore ? (
                  <>
                    <Loading size="sm" />
                    <span className="ml-2">加载中...</span>
                  </>
                ) : (
                  `加载更多（剩余 ${Math.max(0, total - page * PAGE_SIZE)} 条）`
                )}
              </Button>
            </div>
          )}
          {!hasMore && total > PAGE_SIZE && (
            <div className="text-center text-xs text-ink-muted mt-4 mb-4">
              已加载全部 {total} 条结果
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default SearchPage;

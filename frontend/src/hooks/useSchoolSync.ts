import { useEffect, useRef, useCallback } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { schoolsApi } from '../services/schools';
import { useCampusStore } from '../store/useCampusStore';
import { useAuthStore } from '../store/useAuthStore';
import { useUIStore } from '../store/useUIStore';

/**
 * TEN-03.2: 学校同步 Hook
 *
 * 职责：
 * 1. 应用启动时拉取公开学校目录（无需登录）
 * 2. 登录用户拉取 me/memberships，按以下优先级确定当前学校：
 *    a. URL ?school=code 参数（深链接，最高优先级）
 *    b. store 中已持久化的 currentSchoolCode
 *    c. memberships 中的 is_default=true
 *    d. memberships 第一个 active
 *    e. user.school_id 对应学校
 * 3. 监听 URL ?school 变化，自动切换学校
 * 4. 切换学校时：
 *    - cancelQueries：取消所有进行中请求（避免 A→B→A 闪现）
 *    - removeQueries：清除旧学校缓存（按 ['school', oldSchoolId] 前缀精确清理）
 *    - 设置新的 currentSchoolCode（触发 Axios 拦截器注入 X-School-Code）
 *
 * 用法：在根组件 <AppRoutes/> 内最外层调用一次。
 */
export function useSchoolSync(): void {
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const {
    schools,
    setSchools,
    memberships,
    setMemberships,
    setCurrentSchool,
    currentSchoolId,
    currentSchoolCode,
    ensureValidSchool,
    setLoadingSchools,
    setLoadingMemberships,
    loadingMemberships,
  } = useCampusStore();
  const { isAuthenticated, user } = useAuthStore();
  const prevSchoolIdRef = useRef<number | null>(currentSchoolId);
  const hasBootstrappedRef = useRef(false);

  // ----------------------------------------------------------
  // 1. 拉取公开学校目录（始终拉，不依赖登录状态）
  // ----------------------------------------------------------
  const schoolsQuery = useQuery({
    queryKey: ['schools', 'directory'],
    queryFn: async () => {
      setLoadingSchools(true);
      try {
        const list = await schoolsApi.listSchools();
        setSchools(list);
        return list;
      } finally {
        setLoadingSchools(false);
      }
    },
    staleTime: 5 * 60 * 1000,
  });

  // ----------------------------------------------------------
  // 2. 登录后拉取 memberships
  // ----------------------------------------------------------
  useQuery({
    queryKey: ['memberships', user?.id ?? 'anonymous'],
    queryFn: async () => {
      if (!isAuthenticated) return [];
      setLoadingMemberships(true);
      try {
        const list = await schoolsApi.listMyMemberships();
        setMemberships(list);
        return list;
      } finally {
        setLoadingMemberships(false);
      }
    },
    enabled: isAuthenticated,
    staleTime: 60 * 1000,
  });

  // ----------------------------------------------------------
  // 3. 启动 bootstrap：根据 URL ?school / 持久化 / 默认学校确定当前学校
  // ----------------------------------------------------------
  useEffect(() => {
    if (hasBootstrappedRef.current) return;
    if (schoolsQuery.isLoading || schools.length === 0) return;
    // 认证用户需等待 memberships 加载完成，避免选到无权限的学校
    // （如持久化/URL 中残留了用户未加入的学校 code）
    if (isAuthenticated && loadingMemberships) return;

    hasBootstrappedRef.current = true;

    const urlSchoolCode = searchParams.get('school');
    const candidates: Array<{ code: string; source: string }> = [];

    // 认证非 super_admin 用户可访问的学校 code 集合（用于过滤无权限候选）
    const isSuperAdmin = user?.role === 'super_admin';
    const accessibleCodes =
      isAuthenticated && !isSuperAdmin && memberships.length > 0
        ? new Set(
            memberships
              .filter((m) => m.status === 'active')
              .map((m) => m.school.code)
          )
        : null;

    if (urlSchoolCode) {
      // 认证用户：URL 候选需在可访问集合中（super_admin 除外）
      if (!accessibleCodes || accessibleCodes.has(urlSchoolCode)) {
        candidates.push({ code: urlSchoolCode, source: 'url' });
      }
    }
    if (currentSchoolCode) {
      if (!accessibleCodes || accessibleCodes.has(currentSchoolCode)) {
        candidates.push({ code: currentSchoolCode, source: 'persisted' });
      }
    }
    if (isAuthenticated && memberships.length > 0) {
      const def = memberships.find(
        (m) => m.is_default && m.status === 'active'
      );
      if (def) {
        candidates.push({ code: def.school.code, source: 'default' });
      }
      const first = memberships.find((m) => m.status === 'active');
      if (first) {
        candidates.push({ code: first.school.code, source: 'first-active' });
      }
    }
    if (user?.school_id) {
      const userSchool = schools.find((s) => s.id === user.school_id);
      if (userSchool) {
        candidates.push({ code: userSchool.code, source: 'user.school_id' });
      }
    }
    // 没有任何候选时回退到第一所学校
    if (candidates.length === 0 && schools.length > 0) {
      candidates.push({ code: schools[0].code, source: 'fallback' });
    }

    for (const candidate of candidates) {
      const target = schools.find((s) => s.code === candidate.code);
      if (target) {
        setCurrentSchool(target);
        // 同步 URL（仅当 URL 没有该 code 时才写入，避免无谓的 history push）
        if (searchParams.get('school') !== target.code) {
          const next = new URLSearchParams(searchParams);
          next.set('school', target.code);
          setSearchParams(next, { replace: true });
        }
        return;
      }
    }
  }, [
    schools,
    schoolsQuery.isLoading,
    isAuthenticated,
    loadingMemberships,
    memberships,
    user,
    currentSchoolCode,
    searchParams,
    setSearchParams,
    setCurrentSchool,
  ]);

  // ----------------------------------------------------------
  // 4. 监听 URL ?school= 变化，触发学校切换
  // ----------------------------------------------------------
  useEffect(() => {
    const urlCode = searchParams.get('school');
    if (!urlCode) return;
    if (urlCode === currentSchoolCode) return;
    // 找到对应学校并切换
    const target = schools.find((s) => s.code === urlCode);
    if (!target) {
      // 学校不存在（可能未加载完或 code 错误），静默忽略
      return;
    }
    setCurrentSchool(target);
  }, [searchParams, currentSchoolCode, schools, setCurrentSchool]);

  // ----------------------------------------------------------
  // 5. 切换学校时取消进行中请求 + 清除旧缓存
  // ----------------------------------------------------------
  useEffect(() => {
    const prevId = prevSchoolIdRef.current;
    const nextId = currentSchoolId;
    if (prevId === nextId) return;
    prevSchoolIdRef.current = nextId;

    if (prevId !== null) {
      // 取消所有进行中查询（按 ['school', prevId] 前缀）
      // React Query v5：cancelQueries 接受 predicate
      queryClient.cancelQueries({
        predicate: (q) => {
          const key = q.queryKey;
          return Array.isArray(key) && key[0] === 'school' && key[1] === prevId;
        },
      });
      // 清除旧学校缓存（避免 A→B→A 时回到 A 闪现旧数据后 refetch）
      queryClient.removeQueries({
        predicate: (q) => {
          const key = q.queryKey;
          return Array.isArray(key) && key[0] === 'school' && key[1] === prevId;
        },
      });
    }
    // 新学校的查询会因为 queryKey 变化自动触发
  }, [currentSchoolId, queryClient]);

  // ----------------------------------------------------------
  // 6. 登录态变化时：登录后 ensureValidSchool；登出时 clear
  // ACC-01.4: super_admin 可访问所有学校，不调用 ensureValidSchool
  // ----------------------------------------------------------
  useEffect(() => {
    if (!isAuthenticated || memberships.length === 0) return;
    // super_admin 可访问所有学校，跳过 ensureValidSchool 避免被回退
    const isSuperAdmin = user?.role === 'super_admin';
    if (isSuperAdmin) return;

    // prevCode 用实时 store 值（而非 effect 闭包捕获值）：
    // 注册/登录瞬间 setCurrentSchool 与本次 effect 可能在同一次渲染竞态，
    // 闭包旧值会导致"未真正回退"也误判并弹出无权限提示
    const prevCode = useCampusStore.getState().currentSchoolCode;
    ensureValidSchool();
    // ensureValidSchool 可能将无权限学校回退到默认学校，
    // 需同步 URL 避免第 4 步 URL 监听器把学校切回无权限值
    const newCode = useCampusStore.getState().currentSchoolCode;
    if (
      newCode &&
      newCode !== prevCode &&
      searchParams.get('school') !== newCode
    ) {
      const next = new URLSearchParams(searchParams);
      next.set('school', newCode);
      setSearchParams(next, { replace: true });
      // 提示用户无权限，已回退到默认学校
      const fallbackName = useCampusStore.getState().currentSchoolName;
      useUIStore.getState().showToast(
        `您没有该学校的访问权限，已切换回 ${fallbackName}`,
        'info'
      );
    }
  }, [
    isAuthenticated,
    memberships,
    ensureValidSchool,
    currentSchoolCode,
    searchParams,
    setSearchParams,
    user,
  ]);
}

/**
 * TEN-03.3: 切换学校的方法封装
 *
 * - 登录用户：可选是否同时设为默认学校
 * - 切换后写入 URL ?school=code，触发 useSchoolSync 中的 effect
 * - 由调用方决定是否同时调用 PUT /me/default-school
 */
export function useSwitchSchool() {
  const [, setSearchParams] = useSearchParams();
  const { showToast } = useUIStore();

  return useCallback(
    async (code: string, setAsDefault = false) => {
      // ACC-01.4: 普通用户切换前校验是否有目标学校 membership
      // super_admin 可访问所有学校，不校验
      const isSuperAdmin = useAuthStore.getState().user?.role === 'super_admin';
      if (!isSuperAdmin) {
        const { memberships } = useCampusStore.getState();
        const hasAccess = memberships.some(
          (m) => m.school.code === code && m.status === 'active'
        );
        if (!hasAccess) {
          showToast('您没有该学校的访问权限', 'error');
          return;
        }
      }

      // 写入 URL 触发 useSchoolSync 中的切换 effect
      const next = new URLSearchParams(window.location.search);
      next.set('school', code);
      setSearchParams(next, { replace: false });

      if (setAsDefault) {
        try {
          const schools = useCampusStore.getState().schools;
          const target = schools.find((s) => s.code === code);
          if (target) {
            await schoolsApi.setDefaultSchool(target.id);
            showToast(`已将 ${target.name} 设为默认学校`, 'success');
          }
        } catch {
          showToast('设置默认学校失败，请稍后重试', 'error');
        }
      }
    },
    [setSearchParams, showToast]
  );
}

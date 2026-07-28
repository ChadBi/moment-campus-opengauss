import { useMemo } from 'react';
import { useCampusStore } from '../store/useCampusStore';

/**
 * TEN-03.2: 学校感知的 React Query 缓存分区工具
 *
 * 设计原则：
 * - 所有按学校作用域的查询，queryKey 必须以 schoolId 开头
 * - 切换学校时，新 queryKey 与旧的不同，React Query 自动启动新查询
 * - 配合 useSchoolSync 中的 queryClient.cancelQueries() + invalidateQueries()
 *   可保证切换瞬间取消进行中请求，避免 A→B→A 闪现旧数据
 *
 * 使用方式：
 *   const schoolKey = useSchoolQueryKey();
 *   useInfiniteQuery({
 *     queryKey: [...schoolKey, 'posts', 'feed'],
 *     ...
 *   });
 *
 * 注意：返回值经过 useMemo 稳定化，schoolId 不变时引用稳定，
 * 避免作为 useEffect dep 触发无限重渲染。
 */

export function useSchoolQueryKey(): [string, number | null] {
  const schoolId = useCampusStore((s) => s.currentSchoolId);
  return useMemo(() => ['school', schoolId] as [string, number | null], [schoolId]);
}

/**
 * 构造学校作用域 queryKey 的纯函数版本（用于 queryClient.fetchQuery 等场景）
 */
export function buildSchoolQueryKey(
  schoolId: number | null,
  ...rest: unknown[]
): unknown[] {
  return ['school', schoolId, ...rest];
}

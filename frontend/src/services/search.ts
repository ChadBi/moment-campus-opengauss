import { api } from './api';
import type {
  AISearchRequest,
  AISearchResponse,
  PaginatedResponse,
  Post,
} from '../types';

/**
 * DSC-01.1: 搜索筛选参数（与后端 app/api/search.py 对齐）
 *
 * 后端端点 GET /search 支持：
 *   keyword / category_id / location_id / post_type_id / tag
 *   / status（published|expired|valid） / date_from / date_to
 *   / sort（latest|hottest|active） / page / page_size
 *
 * 响应为 PaginatedResponse<Post>（含 total/total_pages/has_more）。
 * 所有 GET 依赖 Axios 拦截器注入的 X-School-Code 头实现租户隔离。
 *
 * AI-02.2: 额外提供 aiSearch 方法对应 POST /search/ai，
 * 支持自然语言查询、可编辑筛选 Chip、匹配理由展示、降级提示。
 */

/** 有效状态筛选 */
export type SearchStatusFilter = 'published' | 'expired' | 'valid';

/** 排序方式（与后端 pattern 对齐） */
export type SearchSort = 'latest' | 'hottest' | 'active';

interface SearchParams {
  keyword?: string;
  category_id?: number;
  location_id?: number;
  post_type_id?: number;
  tag?: string;
  status?: SearchStatusFilter;
  /** ISO 字符串，后端按 created_at >= date_from 过滤 */
  date_from?: string;
  /** ISO 字符串，后端按 created_at <= date_to 过滤 */
  date_to?: string;
  sort?: SearchSort;
  page?: number;
  page_size?: number;
}

export const searchApi = {
  /**
   * DSC-01.1: 普通搜索，支持多维度筛选 + 排序 + 分页
   * 返回 PaginatedResponse<Post>，前端可基于 has_more 判断是否可加载更多。
   */
  search: async (params: SearchParams = {}): Promise<PaginatedResponse<Post>> => {
    // 过滤掉 undefined 值，避免 axios 把 'undefined' 字符串作为参数发送
    const cleaned = Object.fromEntries(
      Object.entries(params).filter(
        ([, v]) => v !== undefined && v !== null && v !== ''
      )
    );
    const response = await api.get('/search', { params: cleaned });
    return response.data;
  },

  /**
   * AI-02.2: AI 结构化搜索
   *
   * 流程：
   * 1. 自然语言 query → 后端调用 AI Provider 解析为结构化意图
   * 2. 用户可在前端编辑筛选 Chip，编辑后通过 overrides 字段覆盖 AI 解析结果
   * 3. 失败时后端降级为普通搜索，返回 fallback=true 与降级原因
   *
   * 响应包含：意图（intent）、匹配理由（match_reasons）、确定性分数（scores）、
   * 降级标记（fallback）、降级原因（fallback_reason）。
   */
  aiSearch: async (payload: AISearchRequest): Promise<AISearchResponse> => {
    const response = await api.post('/search/ai', payload);
    return response.data;
  },
};

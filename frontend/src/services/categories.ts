import { api } from './api';

/**
 * PUB-01.1: 发布表单动态数据来源
 *
 * 后端端点（app/api/categories.py）：
 *   GET /categories      当前学校启用的分类
 *   GET /locations       当前学校地点（含 is_verified 字段）
 *   POST /locations      创建新地点（is_verified=false，进核验队列）
 *
 * 所有 GET 接口依赖 Axios 拦截器注入的 X-School-Code 头实现租户隔离。
 *
 * Task 1.2 调整：移除 GET /post-types 与 PostTypeListItem（PostType 模型已删除，
 * 分类与类型合并为统一「信息分类」5 类：share/teamup/trade/lost_found/other）
 */

/** 分类列表项（后端 CategoryResponse） */
export interface CategoryListItem {
  id: number;
  name: string;
  code: string;
  icon: string;
  description?: string | null;
  sort_order: number;
}

/** 地点列表项（后端 LocationResponse） */
export interface LocationListItem {
  id: number;
  name: string;
  latitude: number;
  longitude: number;
  description?: string | null;
  building?: string | null;
  floor?: string | null;
  /** PUB-01.2：是否已核验（用户自建地点为 false，进核验队列） */
  is_verified: boolean;
}

/** 新建地点请求体 */
export interface CreateLocationRequest {
  name: string;
  latitude: number;
  longitude: number;
  description?: string;
  building?: string;
  floor?: string;
}

export const categoriesApi = {
  /** 获取当前学校启用的分类列表 */
  listCategories: async (): Promise<CategoryListItem[]> => {
    const response = await api.get('/categories');
    return response.data;
  },

  /** 获取当前学校地点列表（含 is_verified 字段） */
  listLocations: async (): Promise<LocationListItem[]> => {
    const response = await api.get('/locations');
    return response.data;
  },

  /** 创建新地点（自动归入当前学校，is_verified=false 进核验队列） */
  createLocation: async (data: CreateLocationRequest): Promise<LocationListItem> => {
    const response = await api.post('/locations', data);
    return response.data;
  },
};

import { api } from './api';
import type { PaginatedResponse } from '../types';

/**
 * TOPIC-01.1: 用户端专题 API
 *
 * 后端端点（app/api/topics.py）：
 *   GET /topics            当前学校已发布专题列表
 *   GET /topics/{id}       专题详情（含关联帖子，仅 published/expired）
 *
 * 租户隔离：通过 Axios 拦截器注入 X-School-Code 头实现跨校隔离。
 * 用户端仅展示 status=published 的专题，draft/archived 不可见。
 */

/** 专题列表项（后端 TopicListItem） */
export interface TopicListItem {
  id: number;
  title: string;
  description?: string | null;
  cover_url?: string | null;
  post_count: number;
  view_count: number;
  sort_order: number;
  published_at?: string | null;
  created_at: string;
}

/** 专题内的帖子项（后端 TopicPostItem） */
export interface TopicPostItem {
  id: number;
  title: string;
  content: string;
  status: string;
  view_count: number;
  like_count: number;
  comment_count: number;
  category_id?: number | null;
  category_name?: string | null;
  post_type_id?: number | null;
  post_type_name?: string | null;
  author_id?: number | null;
  author_name?: string | null;
  cover_image_url?: string | null;
  sort_order: number;
  created_at: string;
}

/** 专题详情（后端 TopicDetail，含关联帖子列表） */
export interface TopicDetail {
  id: number;
  title: string;
  description?: string | null;
  cover_url?: string | null;
  post_count: number;
  view_count: number;
  sort_order: number;
  published_at?: string | null;
  created_at: string;
  posts: TopicPostItem[];
}

export const topicsApi = {
  /** 获取当前学校已发布专题列表 */
  listTopics: async (params?: {
    page?: number;
    page_size?: number;
  }): Promise<PaginatedResponse<TopicListItem>> => {
    const response = await api.get('/topics', { params });
    return response.data;
  },

  /** 获取专题详情（含关联帖子列表） */
  getTopic: async (id: number): Promise<TopicDetail> => {
    const response = await api.get(`/topics/${id}`);
    return response.data;
  },
};

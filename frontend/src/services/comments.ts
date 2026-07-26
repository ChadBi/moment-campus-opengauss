import { api } from './api';
import type { Comment } from '../types';

interface CommentListResponse {
  items: Comment[];
  total: number;
  page: number;
  page_size: number;
}

export const commentsApi = {
  getComments: async (postId: number, page = 1, pageSize = 20): Promise<CommentListResponse> => {
    const response = await api.get(`/posts/${postId}/comments`, {
      params: { page, page_size: pageSize },
    });
    return response.data;
  },

  /**
   * DSC-02.1: 创建评论或回复
   * - 不传 parentId：顶级评论
   * - 传 parentId + replyToUserId：回复指定评论的指定用户（后端会向被回复者发通知）
   */
  createComment: async (
    postId: number,
    content: string,
    parentId?: number,
    replyToUserId?: number
  ): Promise<Comment> => {
    const response = await api.post(`/posts/${postId}/comments`, {
      content,
      parent_id: parentId,
      reply_to_user_id: replyToUserId,
    });
    return response.data;
  },

  deleteComment: async (commentId: number): Promise<void> => {
    await api.delete(`/comments/${commentId}`);
  },
};

import { api } from './api';

interface Comment {
  id: number;
  post_id: number;
  user_id: number;
  parent_id?: number;
  reply_to_user_id?: number;
  content: string;
  like_count: number;
  status: string;
  created_at: string;
  user?: {
    id: number;
    nickname: string;
    avatar_url?: string;
  };
  replies?: Comment[];
}

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

  createComment: async (postId: number, content: string, parentId?: number): Promise<Comment> => {
    const response = await api.post(`/posts/${postId}/comments`, {
      content,
      parent_id: parentId,
    });
    return response.data;
  },

  deleteComment: async (commentId: number): Promise<void> => {
    await api.delete(`/comments/${commentId}`);
  },
};

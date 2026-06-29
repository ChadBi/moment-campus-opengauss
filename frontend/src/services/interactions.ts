import { api } from './api';

export const interactionsApi = {
  likePost: async (postId: number): Promise<{ liked: boolean; like_count: number }> => {
    const response = await api.post(`/posts/${postId}/like`);
    return response.data;
  },

  favoritePost: async (postId: number): Promise<{ favorited: boolean; favorite_count: number }> => {
    const response = await api.post(`/posts/${postId}/favorite`);
    return response.data;
  },

  validatePost: async (
    postId: number,
    validationType: 'valid' | 'invalid' | 'uncertain',
    comment?: string
  ): Promise<{ valid_count: number; invalid_count: number }> => {
    const response = await api.post(`/posts/${postId}/validate`, {
      validation_type: validationType,
      comment,
    });
    return response.data;
  },

  reportPost: async (
    postId: number,
    reportType: string,
    description: string
  ): Promise<void> => {
    await api.post(`/posts/${postId}/report`, {
      report_type: reportType,
      description,
    });
  },

  getMyFavorites: async (page = 1, pageSize = 20): Promise<any> => {
    const response = await api.get('/users/me/favorites', {
      params: { page, page_size: pageSize },
    });
    return response.data;
  },
};

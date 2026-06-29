import { api } from './api';

export const usersApi = {
  getCurrentUser: () => api.get('/users/me'),

  updateUser: (data: { nickname?: string; bio?: string; avatar_url?: string }) =>
    api.put('/users/me', data),

  uploadAvatar: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post('/users/me/avatar', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },

  getMyPosts: (page = 1, pageSize = 20) =>
    api.get('/users/me/posts', { params: { page, page_size: pageSize } }),

  getMyFavorites: (page = 1, pageSize = 20) =>
    api.get('/users/me/favorites', { params: { page, page_size: pageSize } }),
};

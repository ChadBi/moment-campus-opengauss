import { api } from './api';

export const searchApi = {
  search: (
    keyword: string,
    options?: {
      category_id?: number;
      location_name?: string;
      sort_by?: string;
      page?: number;
      page_size?: number;
    }
  ) => {
    const params = { keyword, ...options };
    return api.get('/search', { params });
  },
};

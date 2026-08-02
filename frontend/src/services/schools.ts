import { api } from './api';
import type {
  SchoolSummary,
  Membership,
} from '../store/useCampusStore';

/**
 * TEN-03.2: 学校相关 API 客户端
 *
 * 端点对应后端 app/api/schools.py：
 *   GET    /schools                公开目录
 *   GET    /schools/current        当前学校
 *   GET    /me/memberships         我的学校列表
 *   POST   /schools/{code}/join    加入学校
 *   PUT    /me/default-school      设置默认学校
 */

export interface CurrentSchool extends SchoolSummary {
  address?: string | null;
  /**
   * ADM-02.1: 品牌字段（来自 school_settings 一对一）
   * 后端真实存储，跨浏览器生效；无 settings 行时为 null。
   */
  site_name?: string | null;
  description?: string | null;
  brand_color?: string | null;
}

export interface JoinSchoolResponse {
  membership: Membership;
  already_member: boolean;
}

export interface SetDefaultSchoolResponse {
  default_school_id: number;
  membership: Membership;
}

export const schoolsApi = {
  /** 公开学校目录（无需登录、无需 X-School-Code） */
  listSchools: async (): Promise<SchoolSummary[]> => {
    const response = await api.get('/schools');
    return response.data;
  },

  /** 当前学校（基于 TenantContext，需 X-School-Code） */
  getCurrentSchool: async (): Promise<CurrentSchool> => {
    const response = await api.get('/schools/current');
    return response.data;
  },

  /** 当前用户加入的学校列表（需登录） */
  listMyMemberships: async (): Promise<Membership[]> => {
    const response = await api.get('/me/memberships');
    return response.data;
  },

  /** 加入学校（2026-08-01 起无需邀请码，直接加入；幂等：已是成员返回 already_member=true） */
  joinSchool: async (code: string): Promise<JoinSchoolResponse> => {
    const response = await api.post(`/schools/${code}/join`);
    return response.data;
  },

  /** 设置默认学校 */
  setDefaultSchool: async (
    schoolId: number
  ): Promise<SetDefaultSchoolResponse> => {
    const response = await api.put('/me/default-school', {
      school_id: schoolId,
    });
    return response.data;
  },
};

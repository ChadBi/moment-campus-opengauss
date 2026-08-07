import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { api } from '../services/api';

/**
 * TEN-03.2: 校园（学校）全局 Store
 *
 * 职责：
 * - 维护当前学校（id/code/name/logo/中心点/zoom）
 * - 维护学校目录（公开列表，用于切换组件下拉）
 * - 维护当前用户加入的学校（memberships）
 * - 维护学校公开设置（publicSettings）
 * - 提供 setCurrentSchool / clearSchool / setSchools / setMemberships 方法
 *
 * Axios 拦截器从本 store 读取 currentSchoolCode 注入 X-School-Code 头。
 * React Query 各查询以 currentSchoolId 作为 queryKey 一部分分区缓存。
 *
 * 持久化策略：
 * - 仅持久化 currentSchoolId / currentSchoolCode / currentSchoolName，
 *   学校目录与 memberships 每次登录后从后端拉取，避免脏缓存。
 * - publicSettings 不持久化，每次切校/刷新重新拉取。
 */

export interface SchoolSummary {
  id: number;
  code: string;
  name: string;
  logo_url?: string | null;
  province?: string | null;
  city?: string | null;
  center_lat?: number | null;
  center_lng?: number | null;
  map_zoom?: number | null;
  is_active?: boolean;
  /** B-01': 学校允许的认证域名（公开目录返回，供注册页校验教育邮箱） */
  domains?: string[];
}

export interface MembershipSchoolBrief {
  id: number;
  code: string;
  name: string;
  logo_url?: string | null;
}

export interface Membership {
  id: number;
  school_id: number;
  role: string;
  status: string;
  is_default: boolean;
  joined_at: string;
  school: MembershipSchoolBrief;
}

export interface PublicSettings {
  allow_anonymous: boolean;
  allow_comments: boolean;
  publish_frequency: number;
  image_limit: number;
  default_validity_days: number;
  require_review: boolean;
}

interface CampusState {
  // 当前学校（关键字段：用于 Axios 拦截器与 React Query 缓存分区）
  currentSchoolId: number | null;
  currentSchoolCode: string | null;
  currentSchoolName: string | null;
  currentSchoolLogo: string | null;
  currentSchoolCenter: { lat: number; lng: number } | null;
  currentSchoolZoom: number | null;

  // 学校目录（公开列表）
  schools: SchoolSummary[];

  // 当前用户加入的学校
  memberships: Membership[];

  // 学校公开设置（不做持久化，每次切校/刷新重新拉取）
  publicSettings: PublicSettings | null;
  publicSettingsLoading: boolean;

  // 加载状态（供 UI 显示骨架/占位）
  loadingSchools: boolean;
  loadingMemberships: boolean;

  // 操作
  setCurrentSchool: (school: SchoolSummary) => void;
  setCurrentSchoolById: (id: number) => void;
  clearSchool: () => void;
  setSchools: (schools: SchoolSummary[]) => void;
  setMemberships: (memberships: Membership[]) => void;
  setLoadingSchools: (loading: boolean) => void;
  setLoadingMemberships: (loading: boolean) => void;
  fetchPublicSettings: () => Promise<void>;
  init: () => void;
  /** 切换到下一所已加入的学校（用于快速切换 / 兜底） */
  ensureValidSchool: () => void;
}

export const useCampusStore = create<CampusState>()(
  persist(
    (set, get) => ({
      currentSchoolId: null,
      currentSchoolCode: null,
      currentSchoolName: null,
      currentSchoolLogo: null,
      currentSchoolCenter: null,
      currentSchoolZoom: null,

      schools: [],
      memberships: [],

      publicSettings: null,
      publicSettingsLoading: false,

      loadingSchools: false,
      loadingMemberships: false,

      fetchPublicSettings: async () => {
        const { currentSchoolId } = get();
        if (currentSchoolId === null) return;
        try {
          set({ publicSettingsLoading: true });
          const response = await api.get('/schools/current/settings');
          set({ publicSettings: response.data });
        } catch {
          // 失败不阻塞，保留 null，selector 会走默认值
        } finally {
          set({ publicSettingsLoading: false });
        }
      },

      setCurrentSchool: (school) => {
        set({
          currentSchoolId: school.id,
          currentSchoolCode: school.code,
          currentSchoolName: school.name,
          currentSchoolLogo: school.logo_url ?? null,
          currentSchoolCenter:
            school.center_lat != null && school.center_lng != null
              ? { lat: school.center_lat, lng: school.center_lng }
              : null,
          currentSchoolZoom: school.map_zoom ?? null,
          publicSettings: null,
        });
        void get().fetchPublicSettings();
      },

      setCurrentSchoolById: (id) => {
        const target = get().schools.find((s) => s.id === id);
        if (target) {
          get().setCurrentSchool(target);
        }
      },

      clearSchool: () =>
        set({
          currentSchoolId: null,
          currentSchoolCode: null,
          currentSchoolName: null,
          currentSchoolLogo: null,
          currentSchoolCenter: null,
          currentSchoolZoom: null,
          schools: [],
          memberships: [],
          publicSettings: null,
        }),

      setSchools: (schools) => set({ schools }),

      setMemberships: (memberships) => set({ memberships }),

      setLoadingSchools: (loadingSchools) => set({ loadingSchools }),

      setLoadingMemberships: (loadingMemberships) =>
        set({ loadingMemberships }),

      init: () => {
        const { currentSchoolId } = get();
        if (currentSchoolId !== null) {
          void get().fetchPublicSettings();
        }
      },

      ensureValidSchool: () => {
        // 若当前学校不在已加入学校列表中，回退到默认学校或第一个
        const { memberships, currentSchoolId, schools } = get();
        if (memberships.length === 0) return;
        const stillValid = memberships.some(
          (m) => m.school_id === currentSchoolId && m.status === 'active'
        );
        if (stillValid) return;
        const def = memberships.find((m) => m.is_default && m.status === 'active');
        const fallback = def ?? memberships.find((m) => m.status === 'active');
        if (!fallback) return;
        const school = schools.find((s) => s.id === fallback.school_id);
        if (school) {
          get().setCurrentSchool(school);
        } else {
          // schools 列表尚未加载，仅记录 id/code/name，待加载后补全
          set({
            currentSchoolId: fallback.school.id,
            currentSchoolCode: fallback.school.code,
            currentSchoolName: fallback.school.name,
            currentSchoolLogo: fallback.school.logo_url ?? null,
            publicSettings: null,
          });
          void get().fetchPublicSettings();
        }
      },
    }),
    {
      name: 'campus-storage',
      // 仅持久化当前学校关键字段，列表类数据每次启动重新拉取
      partialize: (state) => ({
        currentSchoolId: state.currentSchoolId,
        currentSchoolCode: state.currentSchoolCode,
        currentSchoolName: state.currentSchoolName,
        currentSchoolLogo: state.currentSchoolLogo,
        currentSchoolCenter: state.currentSchoolCenter,
        currentSchoolZoom: state.currentSchoolZoom,
      }),
    }
  )
);

export const allowAnonymousSelector = (state: CampusState) =>
  state.publicSettings?.allow_anonymous ?? true;

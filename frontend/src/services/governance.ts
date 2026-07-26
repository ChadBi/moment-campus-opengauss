import { api } from './api';
import type {
  ValidationType,
  ValidationAggregation,
  ValidationVote,
  ChangeReportType,
  ChangeReport,
  ChangeReportList,
  ChangeReportStatus,
} from '../types';

// GOV-01: 协同治理服务（2 类投票 + 3 类问题报告）

export const governanceApi = {
  // ===== 2 类互斥投票（confirmation/refutation）=====

  /**
   * 提交有效性投票
   * - 禁止作者给自己投票（后端返回 403）
   * - 每用户每帖一条，第二次提交替换原记录
   */
  votePost: async (
    postId: number,
    validationType: ValidationType,
    comment?: string
  ): Promise<ValidationVote> => {
    const response = await api.post(`/posts/${postId}/validations`, {
      validation_type: validationType,
      comment,
    });
    return response.data;
  },

  /** 聚合投票统计（confirmation_count/refutation_count + 最近记录） */
  getValidationAggregation: async (
    postId: number
  ): Promise<ValidationAggregation> => {
    const response = await api.get(`/posts/${postId}/validations`);
    return response.data;
  },

  // ===== 3 类问题报告（update/expiration_report/conflict_report）=====

  /** 提交问题报告 */
  createChangeReport: async (
    postId: number,
    reportType: ChangeReportType,
    description?: string,
    evidenceUrl?: string
  ): Promise<ChangeReport> => {
    const response = await api.post(`/posts/${postId}/change-reports`, {
      report_type: reportType,
      description,
      evidence_url: evidenceUrl,
    });
    return response.data;
  },

  /** 问题报告列表（含处理状态） */
  listChangeReports: async (
    postId: number,
    statusFilter?: ChangeReportStatus
  ): Promise<ChangeReportList> => {
    const params = statusFilter ? { status_filter: statusFilter } : undefined;
    const response = await api.get(`/posts/${postId}/change-reports`, { params });
    return response.data;
  },

  // ===== 管理员处理 / 作者响应 =====

  /**
   * 处理问题报告
   * - 管理员：可流转至任意状态 open/in_review/resolved/dismissed
   * - 帖子作者：仅可标记为 resolved（标记已更新/已处理）
   */
  handleChangeReport: async (
    reportId: number,
    status: ChangeReportStatus,
    reason?: string
  ): Promise<ChangeReport> => {
    const response = await api.put(`/governance/reports/${reportId}`, {
      status,
      reason,
    });
    return response.data;
  },
};

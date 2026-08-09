import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card } from '../../components/ui/Card';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { Modal } from '../../components/ui/Modal';
import { Input } from '../../components/ui/Input';
import {
  platformApi,
  type SchoolListResponse,
  type SubscriptionHistoryResponse,
  type SchoolAlertsResponse,
  type SubscriptionAssignRequest,
  type SchoolCreateRequest,
} from '../../services/platform';
import { useUIStore } from '../../store/useUIStore';
import { useAuthStore } from '../../store/useAuthStore';
import type { PlatformSchoolDetail, PlatformSubscription } from '../../types';
import {
  RefreshCw,
  School as SchoolIcon,
  Search,
  CheckCircle,
  XCircle,
  Eye,
  Ban,
  Play,
  Plus,
  AlertTriangle,
  History,
  Upload,
} from 'lucide-react';

/** 开通清单项配置 */
const CHECKLIST_ITEMS: Array<{
  key: keyof PlatformSchoolDetail['checklist'];
  label: string;
}> = [
  { key: 'brand_set', label: '品牌已设' },
  { key: 'admin_accepted', label: '管理员已接受' },
  { key: 'locations_imported', label: '地点已导入' },
  { key: 'first_content', label: '首批内容' },
  { key: 'first_members', label: '首批成员' },
];

const PlatformSchoolsPage: React.FC = () => {
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const isSuperAdmin = user?.role === 'super_admin';
  const showToast = useUIStore((s) => s.showToast);

  const [schools, setSchools] = useState<SchoolListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [page, setPage] = useState(1);
  const [keyword, setKeyword] = useState('');
  const [searchInput, setSearchInput] = useState('');

  // 详情弹窗
  const [detailModalOpen, setDetailModalOpen] = useState(false);
  const [detail, setDetail] = useState<PlatformSchoolDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // 历史/告警
  const [history, setHistory] = useState<SubscriptionHistoryResponse | null>(
    null
  );
  const [alerts, setAlerts] = useState<SchoolAlertsResponse | null>(null);

  // 分配套餐弹窗
  const [assignModalOpen, setAssignModalOpen] = useState(false);
  const [assignSchoolId, setAssignSchoolId] = useState<number | null>(null);
  const [assignPlanCode, setAssignPlanCode] = useState('');
  const [assignExpiresAt, setAssignExpiresAt] = useState('');
  const [assignNote, setAssignNote] = useState('');
  const [assigning, setAssigning] = useState(false);

  // 状态切换确认
  const [statusModalOpen, setStatusModalOpen] = useState(false);
  const [statusSchool, setStatusSchool] = useState<{
    id: number;
    name: string;
    is_active: boolean;
  } | null>(null);
  const [statusReason, setStatusReason] = useState('');
  const [statusSubmitting, setStatusSubmitting] = useState(false);

  // 新增学校弹窗
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [createForm, setCreateForm] = useState({
    code: '',
    name: '',
    province: '',
    city: '',
    address: '',
    center_lat: '',
    center_lng: '',
    map_zoom: '15',
    logo_url: '',
    brand_color: '',
    description: '',
    admin_email: '',
    plan_code: '',
  });
  const [createSubmitting, setCreateSubmitting] = useState(false);
  const [plans, setPlans] = useState<Array<{ code: string; name: string }>>([]);

  const loadData = useCallback(async () => {
    try {
      const data = await platformApi.listSchools({
        page,
        page_size: 10,
        keyword: keyword || undefined,
      });
      setSchools(data);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : '加载学校列表失败';
      showToast(message, 'error');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [page, keyword, showToast]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadData();
  }, [loadData]);

  const handleRefresh = () => {
    setRefreshing(true);
    void loadData();
  };

  const handleSearch = () => {
    setKeyword(searchInput);
    setPage(1);
  };

  /** 查看学校详情 */
  const handleViewDetail = async (schoolId: number) => {
    setDetailModalOpen(true);
    setDetailLoading(true);
    setDetail(null);
    setHistory(null);
    setAlerts(null);
    try {
      const [detailData, historyData, alertsData] = await Promise.all([
        platformApi.getSchoolDetail(schoolId),
        platformApi.getSubscriptionHistory(schoolId),
        platformApi.getSchoolAlerts(schoolId),
      ]);
      setDetail(detailData);
      setHistory(historyData);
      setAlerts(alertsData);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : '加载学校详情失败';
      showToast(message, 'error');
    } finally {
      setDetailLoading(false);
    }
  };

  /** 打开分配套餐弹窗 */
  const openAssignModal = (schoolId: number) => {
    setAssignSchoolId(schoolId);
    setAssignPlanCode('');
    setAssignExpiresAt('');
    setAssignNote('');
    setAssignModalOpen(true);
  };

  /** 提交分配套餐 */
  const handleAssign = async () => {
    if (!assignSchoolId || !assignPlanCode) {
      showToast('请选择套餐', 'error');
      return;
    }
    setAssigning(true);
    try {
      const data: SubscriptionAssignRequest = {
        plan_code: assignPlanCode,
        expires_at: assignExpiresAt
          ? new Date(assignExpiresAt).toISOString()
          : null,
        note: assignNote || undefined,
      };
      await platformApi.assignSubscription(assignSchoolId, data);
      showToast('套餐分配成功', 'success');
      setAssignModalOpen(false);
      void loadData();
    } catch (err) {
      const message = err instanceof Error ? err.message : '分配失败';
      showToast(message, 'error');
    } finally {
      setAssigning(false);
    }
  };

  /** 打开状态切换弹窗 */
  const openStatusModal = (school: {
    id: number;
    name: string;
    is_active: boolean;
  }) => {
    setStatusSchool(school);
    setStatusReason('');
    setStatusModalOpen(true);
  };

  /** 提交状态切换 */
  const handleStatusChange = async () => {
    if (!statusSchool) return;
    setStatusSubmitting(true);
    try {
      await platformApi.updateSchoolStatus(statusSchool.id, {
        is_active: !statusSchool.is_active,
        reason: statusReason || undefined,
      });
      showToast(
        statusSchool.is_active ? '学校已暂停' : '学校已启用',
        'success'
      );
      setStatusModalOpen(false);
      void loadData();
    } catch (err) {
      const message = err instanceof Error ? err.message : '操作失败';
      showToast(message, 'error');
    } finally {
      setStatusSubmitting(false);
    }
  };

  /** 打开新增学校弹窗 */
  const openCreateModal = () => {
    setCreateForm({
      code: '',
      name: '',
      province: '',
      city: '',
      address: '',
      center_lat: '',
      center_lng: '',
      map_zoom: '15',
      logo_url: '',
      brand_color: '',
      description: '',
      admin_email: '',
      plan_code: '',
    });
    setCreateModalOpen(true);
    if (plans.length === 0) {
      platformApi.listPlans().then((data) => {
        setPlans(data.filter((p) => p.status === 'active').map((p) => ({ code: p.code, name: p.name })));
      }).catch(() => {});
    }
  };

  /** 提交新增学校 */
  const handleCreateSchool = async () => {
    if (!createForm.code.trim() || !createForm.name.trim()) {
      showToast('请填写学校代码和名称', 'error');
      return;
    }
    setCreateSubmitting(true);
    try {
      const payload: SchoolCreateRequest = {
        code: createForm.code.trim(),
        name: createForm.name.trim(),
        province: createForm.province.trim() || null,
        city: createForm.city.trim() || null,
        address: createForm.address.trim() || null,
        center_lat: createForm.center_lat ? Number(createForm.center_lat) : null,
        center_lng: createForm.center_lng ? Number(createForm.center_lng) : null,
        map_zoom: createForm.map_zoom ? Number(createForm.map_zoom) : null,
        logo_url: createForm.logo_url.trim() || null,
        brand_color: createForm.brand_color.trim() || null,
        description: createForm.description.trim() || null,
        admin_email: createForm.admin_email.trim() || null,
        plan_code: createForm.plan_code || null,
      };
      await platformApi.createSchool(payload);
      showToast('学校创建成功', 'success');
      setCreateModalOpen(false);
      setPage(1);
      void loadData();
    } catch (err) {
      const message = err instanceof Error ? err.message : '创建失败';
      showToast(message, 'error');
    } finally {
      setCreateSubmitting(false);
    }
  };

  if (!isSuperAdmin) {
    return (
      <div className="py-16 text-center">
        <p className="text-ink-sub">仅超级管理员可访问平台学校管理</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="py-16 flex items-center justify-center">
        <div className="flex items-center gap-3 text-ink-muted">
          <div className="w-5 h-5 border-2 border-lake/30 border-t-lake rounded-full animate-spin" />
          <span>加载中...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* 页面标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-ink">学校管理</h1>
          <p className="text-ink-sub text-sm mt-1">
            管理平台学校、开通清单、订阅与告警
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="primary"
            size="sm"
            icon={<Plus size={14} />}
            onClick={openCreateModal}
          >
            新增学校
          </Button>
          <Button
            variant="secondary"
            size="sm"
            icon={<RefreshCw size={14} />}
            loading={refreshing}
            onClick={handleRefresh}
          >
            刷新
          </Button>
        </div>
      </div>

      {/* 搜索栏 */}
      <div className="flex items-center gap-2">
        <Input
          placeholder="按名称或 code 搜索学校"
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') handleSearch();
          }}
          icon={<Search size={16} />}
          className="flex-1"
        />
        <Button variant="primary" size="md" onClick={handleSearch}>
          搜索
        </Button>
      </div>

      {/* 学校列表 */}
      {schools && schools.items.length > 0 ? (
        <Card variant="outlined" padding="none">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-ink-muted border-b border-line">
                  <th className="py-3 px-4 font-medium">学校</th>
                  <th className="py-3 px-4 font-medium">状态</th>
                  <th className="py-3 px-4 font-medium">成员</th>
                  <th className="py-3 px-4 font-medium">内容</th>
                  <th className="py-3 px-4 font-medium">套餐</th>
                  <th className="py-3 px-4 font-medium">操作</th>
                </tr>
              </thead>
              <tbody>
                {schools.items.map((school) => (
                  <tr
                    key={school.id}
                    className="border-b border-line/50 last:border-b-0 hover:bg-paper-hover/50"
                  >
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-2">
                        <div className="w-8 h-8 rounded-md bg-lake/10 grid place-items-center text-lake">
                          <SchoolIcon size={16} />
                        </div>
                        <div>
                          <p className="text-ink font-medium">
                            {school.name}
                          </p>
                          <p className="text-xs text-ink-muted">
                            {school.code}
                          </p>
                        </div>
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <Badge
                        variant={school.is_active ? 'success' : 'danger'}
                      >
                        {school.is_active ? '启用' : '暂停'}
                      </Badge>
                    </td>
                    <td className="py-3 px-4 text-ink-sub">
                      {school.member_count}
                    </td>
                    <td className="py-3 px-4 text-ink-sub">
                      {school.post_count}
                    </td>
                    <td className="py-3 px-4">
                      {school.subscription_plan_code ? (
                        <div className="flex flex-col gap-0.5">
                          <Badge variant="info">
                            {school.subscription_plan_code}
                          </Badge>
                          <span className="text-xs text-ink-muted">
                            {school.subscription_status}
                          </span>
                        </div>
                      ) : (
                        <span className="text-xs text-ink-muted">未开通</span>
                      )}
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-1 flex-wrap">
                        <Button
                          variant="text"
                          size="sm"
                          icon={<Eye size={14} />}
                          onClick={() => handleViewDetail(school.id)}
                        >
                          详情
                        </Button>
                        <Button
                          variant="text"
                          size="sm"
                          className="text-lake"
                          icon={<Plus size={14} />}
                          onClick={() => openAssignModal(school.id)}
                        >
                          分配套餐
                        </Button>
                        <Button
                          variant="text"
                          size="sm"
                          className="text-lamp"
                          icon={<Upload size={14} />}
                          onClick={() =>
                            navigate(
                              `/admin/import?school_id=${school.id}`
                            )
                          }
                        >
                          导入
                        </Button>
                        {school.is_active ? (
                          <Button
                            variant="text"
                            size="sm"
                            className="text-danger"
                            icon={<Ban size={14} />}
                            onClick={() =>
                              openStatusModal({
                                id: school.id,
                                name: school.name,
                                is_active: school.is_active,
                              })
                            }
                          >
                            暂停
                          </Button>
                        ) : (
                          <Button
                            variant="text"
                            size="sm"
                            className="text-grass"
                            icon={<Play size={14} />}
                            onClick={() =>
                              openStatusModal({
                                id: school.id,
                                name: school.name,
                                is_active: school.is_active,
                              })
                            }
                          >
                            启用
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* 分页 */}
          {schools.total_pages > 1 && (
            <div className="flex items-center justify-between px-4 py-3 border-t border-line">
              <span className="text-xs text-ink-muted">
                第 {schools.page} / {schools.total_pages} 页（共 {schools.total} 所）
              </span>
              <div className="flex items-center gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={page <= 1}
                  onClick={() => setPage(page - 1)}
                >
                  上一页
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={page >= schools.total_pages}
                  onClick={() => setPage(page + 1)}
                >
                  下一页
                </Button>
              </div>
            </div>
          )}
        </Card>
      ) : (
        <Card variant="filled" padding="md">
          <p className="text-center text-ink-muted text-sm">暂无学校</p>
        </Card>
      )}

      {/* 学校详情弹窗 */}
      <Modal
        isOpen={detailModalOpen}
        onClose={() => setDetailModalOpen(false)}
        title="学校详情"
        size="lg"
      >
        {detailLoading ? (
          <div className="py-8 flex items-center justify-center">
            <div className="w-5 h-5 border-2 border-lake/30 border-t-lake rounded-full animate-spin" />
          </div>
        ) : detail ? (
          <div className="space-y-5">
            {/* 基本信息 */}
            <div className="flex items-start gap-3">
              <div className="w-12 h-12 rounded-lg bg-lake/10 grid place-items-center text-lake">
                <SchoolIcon size={24} />
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <h3 className="text-lg font-bold text-ink">
                    {detail.name}
                  </h3>
                  <Badge variant="info">{detail.code}</Badge>
                  <Badge variant={detail.is_active ? 'success' : 'danger'}>
                    {detail.is_active ? '启用' : '暂停'}
                  </Badge>
                </div>
                {detail.description && (
                  <p className="text-sm text-ink-muted mt-1">
                    {detail.description}
                  </p>
                )}
                <div className="flex items-center gap-4 mt-2 text-xs text-ink-muted">
                  <span>成员：{detail.member_count}</span>
                  <span>内容：{detail.post_count}</span>
                  <span>分类：{detail.category_count}</span>
                  {detail.subscription_plan_code && (
                    <span>
                      套餐：
                      <Badge variant="info" className="ml-1">
                        {detail.subscription_plan_code}
                      </Badge>
                    </span>
                  )}
                </div>
              </div>
            </div>

            {/* 开通清单 */}
            <div>
              <h4 className="text-sm font-semibold text-ink mb-2">
                开通清单
              </h4>
              <div className="grid grid-cols-5 gap-2">
                {CHECKLIST_ITEMS.map((item) => {
                  const done = detail.checklist[item.key];
                  return (
                    <div
                      key={item.key}
                      className={`flex flex-col items-center gap-1 p-2 rounded-lg ${
                        done
                          ? 'bg-grass/10 text-grass'
                          : 'bg-paper-hover text-ink-muted'
                      }`}
                    >
                      {done ? (
                        <CheckCircle size={18} />
                      ) : (
                        <XCircle size={18} />
                      )}
                      <span className="text-xs text-center">
                        {item.label}
                      </span>
                    </div>
                  );
                })}
              </div>
              {detail.checklist.all_done && (
                <div className="mt-2 flex items-center gap-1.5 text-grass text-sm">
                  <CheckCircle size={14} />
                  <span>全部完成，学校已激活</span>
                </div>
              )}
            </div>

            {/* 告警 */}
            {alerts && alerts.alerts_count > 0 && (
              <div>
                <h4 className="text-sm font-semibold text-ink mb-2 flex items-center gap-1.5">
                  <AlertTriangle size={16} className="text-lamp" />
                  告警（{alerts.alerts_count}）
                </h4>
                <ul className="space-y-1.5">
                  {alerts.alerts.map((alert, idx) => (
                    <li
                      key={idx}
                      className="flex items-start gap-2 text-sm p-2 rounded-lg bg-paper-hover"
                    >
                      <Badge
                        variant={
                          alert.severity === 'critical'
                            ? 'danger'
                            : 'warning'
                        }
                        className="mt-0.5 shrink-0"
                      >
                        {alert.severity === 'critical' ? '严重' : '提醒'}
                      </Badge>
                      <span className="text-ink-sub">{alert.message}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* 套餐历史变更 */}
            {history && history.items.length > 0 && (
              <div>
                <h4 className="text-sm font-semibold text-ink mb-2 flex items-center gap-1.5">
                  <History size={16} className="text-lake" />
                  套餐历史变更（{history.total}）
                </h4>
                <div className="space-y-1.5 max-h-48 overflow-y-auto">
                  {history.items.map((sub: PlatformSubscription) => (
                    <div
                      key={sub.id}
                      className="flex items-center gap-2 text-xs p-2 rounded-lg bg-paper-hover"
                    >
                      <Badge variant="info">{sub.plan_code || '-'}</Badge>
                      <Badge
                        variant={
                          sub.status === 'active' ? 'success' : 'default'
                        }
                      >
                        {sub.status}
                      </Badge>
                      <span className="text-ink-muted">
                        {new Date(sub.assigned_at).toLocaleDateString('zh-CN')}
                      </span>
                      {sub.note && (
                        <span className="text-ink-muted truncate">
                          · {sub.note}
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="flex items-center justify-end gap-2 pt-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setDetailModalOpen(false)}
              >
                关闭
              </Button>
              <Button
                variant="primary"
                size="sm"
                icon={<Plus size={14} />}
                onClick={() => {
                  setDetailModalOpen(false);
                  openAssignModal(detail.id);
                }}
              >
                分配套餐
              </Button>
            </div>
          </div>
        ) : (
          <p className="text-center text-ink-muted py-8">加载失败</p>
        )}
      </Modal>

      {/* 分配套餐弹窗 */}
      <AssignPlanModal
        isOpen={assignModalOpen}
        onClose={() => setAssignModalOpen(false)}
        schoolId={assignSchoolId}
        planCode={assignPlanCode}
        expiresAt={assignExpiresAt}
        note={assignNote}
        onPlanCodeChange={setAssignPlanCode}
        onExpiresAtChange={setAssignExpiresAt}
        onNoteChange={setAssignNote}
        onSubmit={handleAssign}
        submitting={assigning}
      />

      {/* 状态切换弹窗 */}
      <Modal
        isOpen={statusModalOpen}
        onClose={() => setStatusModalOpen(false)}
        title={statusSchool?.is_active ? '暂停学校' : '启用学校'}
        size="sm"
      >
        <div className="space-y-4">
          <p className="text-sm text-ink-sub">
            确定要{statusSchool?.is_active ? '暂停' : '启用'}学校 "
            <span className="font-medium text-ink">
              {statusSchool?.name}
            </span>
            " 吗？
            {statusSchool?.is_active && (
              <span className="block mt-1 text-xs text-danger">
                暂停后该校将无法新增写入，已有内容仍可浏览。
              </span>
            )}
          </p>
          <div>
            <label className="block text-sm font-medium text-ink mb-1.5">
              原因（可选）
            </label>
            <textarea
              value={statusReason}
              onChange={(e) => setStatusReason(e.target.value)}
              rows={3}
              placeholder="操作原因说明"
              className="w-full px-3.5 py-2 bg-paper border border-line rounded-[10px] text-sm text-ink placeholder:text-ink-muted/60 focus:outline-none focus:border-lake resize-none"
            />
          </div>
          <div className="flex items-center justify-end gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setStatusModalOpen(false)}
            >
              取消
            </Button>
            <Button
              variant={statusSchool?.is_active ? 'danger' : 'primary'}
              size="sm"
              loading={statusSubmitting}
              onClick={handleStatusChange}
            >
              确定
            </Button>
          </div>
        </div>
      </Modal>

      {/* 新增学校弹窗 */}
      <Modal
        isOpen={createModalOpen}
        onClose={() => setCreateModalOpen(false)}
        title="新增学校"
        size="md"
      >
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <Input
              label="学校代码"
              placeholder="如 jiangnan"
              value={createForm.code}
              onChange={(e) => setCreateForm({ ...createForm, code: e.target.value })}
              required
            />
            <Input
              label="学校名称"
              placeholder="如 江南大学"
              value={createForm.name}
              onChange={(e) => setCreateForm({ ...createForm, name: e.target.value })}
              required
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Input
              label="省份"
              placeholder="如 江苏省"
              value={createForm.province}
              onChange={(e) => setCreateForm({ ...createForm, province: e.target.value })}
            />
            <Input
              label="城市"
              placeholder="如 无锡市"
              value={createForm.city}
              onChange={(e) => setCreateForm({ ...createForm, city: e.target.value })}
            />
          </div>
          <Input
            label="详细地址（可选）"
            placeholder="如 江苏省无锡市滨湖区蠡湖大道1800号"
            value={createForm.address}
            onChange={(e) => setCreateForm({ ...createForm, address: e.target.value })}
          />
          <div className="grid grid-cols-3 gap-3">
            <Input
              label="中心纬度"
              type="number"
              step="0.000001"
              placeholder="31.483652"
              value={createForm.center_lat}
              onChange={(e) => setCreateForm({ ...createForm, center_lat: e.target.value })}
            />
            <Input
              label="中心经度"
              type="number"
              step="0.000001"
              placeholder="120.27116"
              value={createForm.center_lng}
              onChange={(e) => setCreateForm({ ...createForm, center_lng: e.target.value })}
            />
            <Input
              label="地图缩放"
              type="number"
              min="1"
              max="20"
              placeholder="15"
              value={createForm.map_zoom}
              onChange={(e) => setCreateForm({ ...createForm, map_zoom: e.target.value })}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Input
              label="Logo URL（可选）"
              placeholder="https://example.com/logo.png"
              value={createForm.logo_url}
              onChange={(e) => setCreateForm({ ...createForm, logo_url: e.target.value })}
            />
            <Input
              label="品牌色（可选）"
              placeholder="#174d5e"
              value={createForm.brand_color}
              onChange={(e) => setCreateForm({ ...createForm, brand_color: e.target.value })}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-ink mb-1.5">
              初始套餐
            </label>
            <select
              value={createForm.plan_code}
              onChange={(e) => setCreateForm({ ...createForm, plan_code: e.target.value })}
              className="select-nice"
            >
              <option value="">不分配套餐</option>
              {plans.map((p) => (
                <option key={p.code} value={p.code}>
                  {p.name}（{p.code}）
                </option>
              ))}
            </select>
          </div>
          <Input
            label="管理员邮箱（可选）"
            type="email"
            placeholder="admin@school.edu.cn"
            value={createForm.admin_email}
            onChange={(e) => setCreateForm({ ...createForm, admin_email: e.target.value })}
          />
          <div>
            <label className="block text-sm font-medium text-ink mb-1.5">
              描述（可选）
            </label>
            <textarea
              value={createForm.description}
              onChange={(e) => setCreateForm({ ...createForm, description: e.target.value })}
              rows={2}
              placeholder="学校简介"
              className="w-full px-3.5 py-2 bg-paper border border-line rounded-[10px] text-sm text-ink placeholder:text-ink-muted/60 focus:outline-none focus:border-lake resize-none"
            />
          </div>
          <div className="flex items-center justify-end gap-2 pt-2">
            <Button variant="secondary" size="sm" onClick={() => setCreateModalOpen(false)}>
              取消
            </Button>
            <Button
              variant="primary"
              size="sm"
              loading={createSubmitting}
              icon={<Plus size={14} />}
              onClick={handleCreateSchool}
            >
              创建学校
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
};

/** 分配套餐子组件（避免主组件过载） */
interface AssignPlanModalProps {
  isOpen: boolean;
  onClose: () => void;
  schoolId: number | null;
  planCode: string;
  expiresAt: string;
  note: string;
  onPlanCodeChange: (v: string) => void;
  onExpiresAtChange: (v: string) => void;
  onNoteChange: (v: string) => void;
  onSubmit: () => void;
  submitting: boolean;
}

const AssignPlanModal: React.FC<AssignPlanModalProps> = ({
  isOpen,
  onClose,
  planCode,
  expiresAt,
  note,
  onPlanCodeChange,
  onExpiresAtChange,
  onNoteChange,
  onSubmit,
  submitting,
}) => {
  const [plans, setPlans] = useState<Array<{ code: string; name: string }>>(
    []
  );

  useEffect(() => {
    if (isOpen && plans.length === 0) {
      void platformApi.listPlans().then((data) => {
        setPlans(
          data
            .filter((p) => p.status === 'active')
            .map((p) => ({ code: p.code, name: p.name }))
        );
      });
    }
  }, [isOpen, plans.length]);

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="分配套餐" size="md">
      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-ink mb-1.5">
            套餐
            <span className="text-danger ml-1">*</span>
          </label>
          <select
            value={planCode}
            onChange={(e) => onPlanCodeChange(e.target.value)}
            className="select-nice"
          >
            <option value="">请选择套餐</option>
            {plans.map((p) => (
              <option key={p.code} value={p.code}>
                {p.name}（{p.code}）
              </option>
            ))}
          </select>
        </div>
        <Input
          label="到期时间（可选）"
          type="datetime-local"
          value={expiresAt}
          onChange={(e) => onExpiresAtChange(e.target.value)}
        />
        <div>
          <label className="block text-sm font-medium text-ink mb-1.5">
            备注
          </label>
          <textarea
            value={note}
            onChange={(e) => onNoteChange(e.target.value)}
            rows={3}
            placeholder="分配原因"
            className="w-full px-3.5 py-2 bg-paper border border-line rounded-[10px] text-sm text-ink placeholder:text-ink-muted/60 focus:outline-none focus:border-lake resize-none"
          />
        </div>
        <div className="flex items-center justify-end gap-2 pt-2">
          <Button variant="secondary" size="sm" onClick={onClose}>
            取消
          </Button>
          <Button
            variant="primary"
            size="sm"
            loading={submitting}
            icon={<Plus size={14} />}
            onClick={onSubmit}
          >
            分配
          </Button>
        </div>
      </div>
    </Modal>
  );
};

export default PlatformSchoolsPage;

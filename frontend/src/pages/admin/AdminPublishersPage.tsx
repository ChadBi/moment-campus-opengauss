import React, { useCallback, useEffect, useState } from 'react';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Badge } from '../../components/ui/Badge';
import { Input } from '../../components/ui/Input';
import { Modal } from '../../components/ui/Modal';
import { Table, Pagination, type Column } from '../../components/ui/Table';
import { adminApi } from '../../services/admin';
import { useUIStore } from '../../store/useUIStore';
import type {
  PublisherAdmin,
  PublisherVerifiedStatus,
  PublisherType,
  PublisherVerifyAction,
  PublisherMembershipBrief,
  PublisherMemberRole,
} from '../../types';
import {
  Building2,
  CheckCircle2,
  XCircle,
  RotateCcw,
  Trash2,
  Users,
  Search,
  ShieldCheck,
} from 'lucide-react';
import { formatShortDateTime } from '../../utils/date';

const PAGE_SIZE = 10;

const TYPE_LABELS: Record<PublisherType, string> = {
  department: '部门',
  club: '社团',
  service_org: '服务组织',
};

const STATUS_LABELS: Record<PublisherVerifiedStatus, { label: string; variant: 'success' | 'warning' | 'danger' | 'default' }> = {
  pending: { label: '待认证', variant: 'warning' },
  verified: { label: '已认证', variant: 'success' },
  revoked: { label: '已撤销', variant: 'danger' },
  rejected: { label: '已驳回', variant: 'default' },
};

/** ORG-01.2: 校级 admin 发布主体管理（审核/认证/撤销/成员） */
const AdminPublishersPage: React.FC = () => {
  const showToast = useUIStore((s) => s.showToast);
  const [items, setItems] = useState<PublisherAdmin[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [keyword, setKeyword] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [statusFilter, setStatusFilter] = useState<PublisherVerifiedStatus | ''>('');
  const [typeFilter, setTypeFilter] = useState<PublisherType | ''>('');
  const [actingId, setActingId] = useState<number | null>(null);

  // 审核弹窗
  const [verifyTarget, setVerifyTarget] = useState<PublisherAdmin | null>(null);
  const [verifyAction, setVerifyAction] = useState<PublisherVerifyAction>('approve');
  const [verifyNote, setVerifyNote] = useState('');
  const [verifySubmitting, setVerifySubmitting] = useState(false);

  // 成员管理弹窗
  const [membersTarget, setMembersTarget] = useState<PublisherAdmin | null>(null);

  const loadList = useCallback(async (p: number) => {
    try {
      setLoading(true);
      const data = await adminApi.getPublishers({
        page: p,
        page_size: PAGE_SIZE,
        keyword: keyword || undefined,
        verified_status: statusFilter || undefined,
        type: typeFilter || undefined,
      });
      setItems(data.items);
      setTotal(data.total);
      setTotalPages(data.total_pages);
    } catch (err) {
      const msg = err instanceof Error ? err.message : '加载失败';
      showToast(msg, 'error');
    } finally {
      setLoading(false);
    }
  }, [keyword, statusFilter, typeFilter, showToast]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setPage(1);
    void loadList(1);
  }, [loadList]);

  useEffect(() => {
    void loadList(page);
  }, [page, loadList]);

  const handleSearch = () => {
    setKeyword(searchInput);
  };

  // 打开审核弹窗
  const openVerify = (item: PublisherAdmin, action: PublisherVerifyAction) => {
    setVerifyTarget(item);
    setVerifyAction(action);
    setVerifyNote('');
  };

  // 提交审核
  const submitVerify = async () => {
    if (!verifyTarget) return;
    try {
      setVerifySubmitting(true);
      await adminApi.verifyPublisher(verifyTarget.id, verifyAction, verifyNote || undefined);
      const labels: Record<PublisherVerifyAction, string> = {
        approve: '认证通过',
        reject: '已驳回申请',
        revoke: '已撤销认证',
        restore: '已恢复待审核',
      };
      showToast(`${labels[verifyAction]}：${verifyTarget.name}`, 'success');
      setVerifyTarget(null);
      void loadList(page);
    } catch (err) {
      const msg = err instanceof Error ? err.message : '操作失败';
      showToast(msg, 'error');
    } finally {
      setVerifySubmitting(false);
    }
  };

  // 软删除
  const handleDelete = async (item: PublisherAdmin) => {
    if (!window.confirm(`确定要删除发布主体「${item.name}」吗？`)) return;
    try {
      setActingId(item.id);
      await adminApi.deletePublisher(item.id);
      showToast(`已删除：${item.name}`, 'success');
      void loadList(page);
    } catch (err) {
      const msg = err instanceof Error ? err.message : '删除失败';
      showToast(msg, 'error');
    } finally {
      setActingId(null);
    }
  };

  const formatDate = (dateString?: string) =>
    dateString ? formatShortDateTime(dateString) : '—';

  const columns: Column<PublisherAdmin>[] = [
    {
      key: 'name',
      title: '主体名称',
      render: (value, row) => (
        <div className="min-w-0">
          <p className="font-medium text-ink line-clamp-1">{value}</p>
          <p className="text-xs text-ink-muted line-clamp-1 mt-0.5">
            {row.intro || '—'}
          </p>
        </div>
      ),
    },
    {
      key: 'type',
      title: '类型',
      width: 90,
      nowrap: true,
      render: (value) => <Badge variant="default">{TYPE_LABELS[value as PublisherType]}</Badge>,
    },
    {
      key: 'verified_status',
      title: '认证状态',
      width: 100,
      nowrap: true,
      render: (value) => {
        const info = STATUS_LABELS[value as PublisherVerifiedStatus];
        return <Badge variant={info.variant}>{info.label}</Badge>;
      },
    },
    {
      key: 'member_count',
      title: '成员',
      width: 70,
      nowrap: true,
      render: (value) => `${value} 人`,
    },
    {
      key: 'view_count',
      title: '浏览/订阅',
      width: 110,
      nowrap: true,
      render: (value, row) => (
        <span className="text-xs text-ink-sub">
          {value} / {row.subscribe_count}
        </span>
      ),
    },
    {
      key: 'verified_at',
      title: '认证时间',
      width: 130,
      nowrap: true,
      render: (value) => formatDate(value as string | undefined),
    },
    {
      key: 'actions',
      title: '操作',
      width: 240,
      nowrap: true,
      render: (_, row) => {
        const status = row.verified_status;
        return (
          <div className="flex items-center gap-1 flex-wrap">
            {/* 认证状态相关操作 */}
            {status === 'pending' && (
              <>
                <Button
                  size="sm"
                  variant="primary"
                  onClick={() => openVerify(row, 'approve')}
                >
                  <CheckCircle2 size={12} className="mr-0.5" />
                  认证
                </Button>
                <Button
                  size="sm"
                  variant="text"
                  onClick={() => openVerify(row, 'reject')}
                >
                  <XCircle size={12} className="mr-0.5" />
                  驳回
                </Button>
              </>
            )}
            {status === 'verified' && (
              <Button
                size="sm"
                variant="text"
                onClick={() => openVerify(row, 'revoke')}
              >
                <XCircle size={12} className="mr-0.5" />
                撤销
              </Button>
            )}
            {(status === 'revoked' || status === 'rejected') && (
              <Button
                size="sm"
                variant="text"
                onClick={() => openVerify(row, 'restore')}
              >
                <RotateCcw size={12} className="mr-0.5" />
                恢复
              </Button>
            )}
            <Button
              size="sm"
              variant="text"
              onClick={() => setMembersTarget(row)}
            >
              <Users size={12} className="mr-0.5" />
              成员
            </Button>
            <Button
              size="sm"
              variant="text"
              loading={actingId === row.id}
              onClick={() => handleDelete(row)}
              className="text-danger hover:bg-danger/10"
            >
              <Trash2 size={12} className="mr-0.5" />
              删除
            </Button>
          </div>
        );
      },
    },
  ];

  return (
    <div className="space-y-4">
      {/* 页面标题 */}
      <div>
        <h1 className="text-2xl font-bold text-ink flex items-center gap-2">
          <Building2 size={22} />
          发布主体管理
        </h1>
        <p className="text-ink-sub text-sm mt-1">
          审核/认证/撤销/恢复发布主体，管理成员 · 共 {total} 个主体
        </p>
      </div>

      {/* 认证说明 */}
      <div className="bg-info/5 border border-info/20 rounded-lg p-3 text-xs text-info flex items-start gap-2">
        <ShieldCheck size={14} className="flex-shrink-0 mt-0.5" />
        <div>
          <p className="font-medium mb-0.5">认证规则</p>
          <p>认证标识不可由用户自行设置，仅本页可流转 verified_status。认证不代表内容免审——发布主体关联帖子仍走原 post_status 审核流程。</p>
        </div>
      </div>

      {/* 筛选栏 */}
      <Card variant="outlined" padding="sm">
        <div className="flex flex-wrap items-center gap-2">
          {/* 状态筛选 */}
          {([
            { value: '', label: '全部状态' },
            { value: 'pending', label: '待认证' },
            { value: 'verified', label: '已认证' },
            { value: 'revoked', label: '已撤销' },
            { value: 'rejected', label: '已驳回' },
          ] as const).map((opt) => (
            <button
              key={opt.value}
              onClick={() => setStatusFilter(opt.value)}
              className={`px-3 py-1.5 rounded-md text-xs transition-colors ${
                statusFilter === opt.value
                  ? 'bg-lake text-paper'
                  : 'bg-mist text-ink-sub hover:text-ink'
              }`}
            >
              {opt.label}
            </button>
          ))}
          {/* 类型筛选 */}
          <div className="w-px h-5 bg-ink-divider mx-1" />
          {([
            { value: '', label: '全部类型' },
            { value: 'department', label: '部门' },
            { value: 'club', label: '社团' },
            { value: 'service_org', label: '服务组织' },
          ] as const).map((opt) => (
            <button
              key={opt.value}
              onClick={() => setTypeFilter(opt.value)}
              className={`px-3 py-1.5 rounded-md text-xs transition-colors ${
                typeFilter === opt.value
                  ? 'bg-lake text-paper'
                  : 'bg-mist text-ink-sub hover:text-ink'
              }`}
            >
              {opt.label}
            </button>
          ))}
          <div className="flex items-center gap-2 ml-auto">
            <Input
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              placeholder="按名称搜索"
              className="w-44"
            />
            <Button size="sm" variant="secondary" onClick={handleSearch}>
              <Search size={13} className="mr-1" />
              搜索
            </Button>
          </div>
        </div>
      </Card>

      {/* 表格 */}
      {items.length === 0 && !loading ? (
        <Card padding="lg" className="text-center py-16">
          <Building2 size={48} className="mx-auto text-ink-disabled mb-4" />
          <p className="text-ink-sub">暂无发布主体</p>
        </Card>
      ) : (
        <Table<PublisherAdmin>
          columns={columns}
          data={items}
          loading={loading}
          emptyText="暂无发布主体"
        />
      )}

      {/* 分页 */}
      <Pagination
        page={page}
        pageSize={PAGE_SIZE}
        total={total}
        totalPages={totalPages}
        onChange={(p) => setPage(p)}
      />

      {/* 审核弹窗 */}
      {verifyTarget && (
        <Modal
          isOpen
          onClose={() => setVerifyTarget(null)}
          title={`${_ACTION_LABELS[verifyAction]}：${verifyTarget.name}`}
          size="md"
        >
          <div className="px-6 py-5 space-y-4">
            <div className="flex items-center gap-2">
              <Badge variant="default">{TYPE_LABELS[verifyTarget.type]}</Badge>
              <span className="text-sm text-ink-sub">
                当前状态：
                <Badge variant={STATUS_LABELS[verifyTarget.verified_status].variant} className="ml-1">
                  {STATUS_LABELS[verifyTarget.verified_status].label}
                </Badge>
              </span>
            </div>
            {verifyTarget.intro && (
              <div className="text-sm text-ink-sub bg-mist/40 rounded-lg p-3">
                {verifyTarget.intro}
              </div>
            )}
            <div>
              <label className="block text-sm font-medium text-ink mb-1">
                {_ACTION_LABELS[verifyAction]}原因 / 备注
              </label>
              <textarea
                value={verifyNote}
                onChange={(e) => setVerifyNote(e.target.value)}
                placeholder="请填写审核备注（可选）"
                maxLength={500}
                rows={3}
                className="w-full px-3 py-2 rounded-[10px] border border-line bg-paper text-ink text-sm placeholder:text-ink-disabled focus:outline-none focus:border-lake transition-colors"
              />
            </div>
          </div>
          <div className="flex justify-end gap-2 px-6 py-4 border-t border-ink-divider bg-mist/30">
            <Button variant="text" onClick={() => setVerifyTarget(null)} disabled={verifySubmitting}>
              取消
            </Button>
            <Button
              variant={verifyAction === 'approve' ? 'primary' : 'secondary'}
              onClick={submitVerify}
              loading={verifySubmitting}
            >
              确认{_ACTION_LABELS[verifyAction]}
            </Button>
          </div>
        </Modal>
      )}

      {/* 成员管理弹窗 */}
      {membersTarget && (
        <MembersModal
          publisher={membersTarget}
          onClose={() => setMembersTarget(null)}
          showToast={showToast}
        />
      )}
    </div>
  );
};

const _ACTION_LABELS: Record<PublisherVerifyAction, string> = {
  approve: '认证通过',
  reject: '驳回申请',
  revoke: '撤销认证',
  restore: '恢复待审核',
};

// ============================================================
// 成员管理弹窗
// ============================================================
interface MembersModalProps {
  publisher: PublisherAdmin;
  onClose: () => void;
  showToast: (msg: string, type?: 'success' | 'error' | 'warning' | 'info') => void;
}

const MembersModal: React.FC<MembersModalProps> = ({ publisher, onClose, showToast }) => {
  const [members, setMembers] = useState<PublisherMembershipBrief[]>([]);
  const [loading, setLoading] = useState(true);
  const [actingUserId, setActingUserId] = useState<number | null>(null);
  const [addUserId, setAddUserId] = useState('');
  const [addRole, setAddRole] = useState<PublisherMemberRole>('member');

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const data = await adminApi.getPublisherMembers(publisher.id);
      setMembers(data);
    } catch (err) {
      const msg = err instanceof Error ? err.message : '加载失败';
      showToast(msg, 'error');
    } finally {
      setLoading(false);
    }
  }, [publisher.id, showToast]);

  useEffect(() => {
    void load();
  }, [load]);

  const handleAdd = async () => {
    const uid = Number(addUserId);
    if (!uid) {
      showToast('请输入用户 ID', 'warning');
      return;
    }
    try {
      await adminApi.addPublisherMember(publisher.id, uid, addRole);
      showToast('已添加成员', 'success');
      setAddUserId('');
      void load();
    } catch (err) {
      const msg = err instanceof Error ? err.message : '添加失败';
      showToast(msg, 'error');
    }
  };

  const handleRoleChange = async (userId: number, role: PublisherMemberRole) => {
    try {
      setActingUserId(userId);
      await adminApi.updatePublisherMember(publisher.id, userId, role);
      showToast('已更新角色', 'success');
      void load();
    } catch (err) {
      const msg = err instanceof Error ? err.message : '更新失败';
      showToast(msg, 'error');
    } finally {
      setActingUserId(null);
    }
  };

  const handleRemove = async (userId: number, nickname?: string | null) => {
    if (!window.confirm(`确定移除成员「${nickname || `用户${userId}`}」？`)) return;
    try {
      setActingUserId(userId);
      await adminApi.removePublisherMember(publisher.id, userId);
      showToast('已移除成员', 'success');
      void load();
    } catch (err) {
      const msg = err instanceof Error ? err.message : '移除失败';
      showToast(msg, 'error');
    } finally {
      setActingUserId(null);
    }
  };

  return (
    <Modal isOpen onClose={onClose} title={`成员管理：${publisher.name}`} size="lg">
      <div className="px-6 py-5 space-y-4">
        {/* 添加成员 */}
        <div className="bg-mist/30 rounded-lg p-3">
          <p className="text-sm font-medium text-ink mb-2">添加成员</p>
          <div className="flex items-center gap-2">
            <Input
              value={addUserId}
              onChange={(e) => setAddUserId(e.target.value)}
              placeholder="用户 ID"
              className="w-32"
              type="number"
            />
            <select
              value={addRole}
              onChange={(e) => setAddRole(e.target.value as PublisherMemberRole)}
              className="px-3 py-2 rounded-[10px] border border-line bg-paper text-ink text-sm focus:outline-none focus:border-lake"
            >
              <option value="member">成员</option>
              <option value="admin">管理员</option>
              <option value="owner">负责人</option>
            </select>
            <Button size="sm" variant="primary" onClick={handleAdd}>
              添加
            </Button>
          </div>
        </div>

        {/* 成员列表 */}
        {loading ? (
          <p className="text-center text-ink-sub py-8">加载中...</p>
        ) : members.length === 0 ? (
          <p className="text-center text-ink-sub py-8">暂无成员</p>
        ) : (
          <div className="space-y-2">
            {members.map((m) => (
              <div
                key={m.id}
                className="flex items-center gap-3 p-3 rounded-lg bg-mist/30"
              >
                <div className="w-8 h-8 rounded-full bg-paper-hover flex items-center justify-center text-xs font-medium text-ink-sub flex-shrink-0">
                  {m.user_nickname?.charAt(0) || '?'}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-ink line-clamp-1">
                    {m.user_nickname || `用户${m.user_id}`}
                  </p>
                  <p className="text-xs text-ink-muted">{m.user_email}</p>
                </div>
                <select
                  value={m.role}
                  onChange={(e) => handleRoleChange(m.user_id, e.target.value as PublisherMemberRole)}
                  disabled={actingUserId === m.user_id}
                  className="px-2 py-1 rounded-md border border-line bg-paper text-ink text-xs focus:outline-none focus:border-lake disabled:opacity-50"
                >
                  <option value="member">成员</option>
                  <option value="admin">管理员</option>
                  <option value="owner">负责人</option>
                </select>
                <Button
                  size="sm"
                  variant="text"
                  loading={actingUserId === m.user_id}
                  onClick={() => handleRemove(m.user_id, m.user_nickname)}
                  className="text-danger hover:bg-danger/10"
                >
                  移除
                </Button>
              </div>
            ))}
          </div>
        )}
      </div>
      <div className="flex justify-end px-6 py-4 border-t border-ink-divider bg-mist/30">
        <Button variant="text" onClick={onClose}>
          关闭
        </Button>
      </div>
    </Modal>
  );
};

export default AdminPublishersPage;

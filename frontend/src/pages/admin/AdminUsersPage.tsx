import React, { useState, useEffect, useCallback } from 'react';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Badge } from '../../components/ui/Badge';
import { Avatar } from '../../components/ui/Avatar';
import { Table, Pagination, type Column } from '../../components/ui/Table';
import { adminApi, type UserBrief } from '../../services/admin';
import { useAuthStore } from '../../store/useAuthStore';
import { Users, UserCheck, UserX } from 'lucide-react';
import { logger } from '../../utils/logger';
import { formatDate } from '../../utils/date';

const PAGE_SIZE = 10;

/** 角色标签映射 */
const ROLE_LABELS: Record<string, { label: string; variant: 'default' | 'info' | 'warning' }> = {
  user: { label: '普通用户', variant: 'default' },
  admin: { label: '管理员', variant: 'info' },
  super_admin: { label: '超级管理员', variant: 'warning' },
};

const AdminUsersPage: React.FC = () => {
  const { user: currentUser } = useAuthStore();
  const [users, setUsers] = useState<UserBrief[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [selectedKeys, setSelectedKeys] = useState<Array<string | number>>([]);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'warning' } | null>(null);
  const [batchLoading, setBatchLoading] = useState(false);
  const [filterActive, setFilterActive] = useState<boolean | undefined>(undefined);

  const loadUsers = useCallback(async (p: number, active?: boolean) => {
    try {
      const data = await adminApi.getUsers({ page: p, page_size: PAGE_SIZE, is_active: active });
      setUsers(data.items);
      setTotal(data.total);
      setTotalPages(data.total_pages);
      setSelectedKeys([]);
    } catch (error) {
      logger.error('加载用户列表失败:', error);
      setToast({ message: '加载用户列表失败', type: 'error' });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadUsers(page, filterActive);
  }, [page, filterActive, loadUsers]);

  /** 单条切换状态 */
  const handleToggleActive = async (userId: number, currentActive: boolean) => {
    // 不允许操作自己
    if (userId === currentUser?.id) {
      setToast({ message: '不能修改自己的状态', type: 'warning' });
      return;
    }
    const action = currentActive ? '禁用' : '启用';
    if (!window.confirm(`确定要${action}该用户吗？`)) return;

    try {
      await adminApi.toggleUserActive(userId, {
        is_active: !currentActive,
      });
      setToast({ message: `${action}成功`, type: 'success' });
      loadUsers(page, filterActive);
    } catch (error) {
      logger.error(`${action}失败:`, error);
      setToast({ message: `${action}失败`, type: 'error' });
    }
  };

  /** 批量启用/禁用 */
  const handleBatchToggle = async (targetActive: boolean) => {
    if (selectedKeys.length === 0) return;
    const action = targetActive ? '启用' : '禁用';
    if (!window.confirm(`确定要批量${action} ${selectedKeys.length} 个用户吗？`)) return;

    setBatchLoading(true);
    try {
      const result = await adminApi.batchToggleUsersActive({
        user_ids: selectedKeys as number[],
        is_active: targetActive,
      });
      setToast({ message: result.message, type: result.failed > 0 ? 'warning' : 'success' });
      loadUsers(page, filterActive);
    } catch (error) {
      logger.error(`批量${action}失败:`, error);
      setToast({ message: `批量${action}失败`, type: 'error' });
    } finally {
      setBatchLoading(false);
    }
  };

  // 表格列配置
  const columns: Column<UserBrief>[] = [
    {
      key: 'nickname',
      title: '用户',
      render: (value, row) => (
        <div className="flex items-center gap-2.5 min-w-0">
          <Avatar
            fallback={value?.[0] || '?'}
            size="sm"
          />
          <div className="min-w-0">
            <p className="font-medium text-ink truncate">{value}</p>
            <p className="text-xs text-ink-muted truncate">{row.phone ? `${row.phone.slice(0, 3)}****${row.phone.slice(-4)}` : '无手机号'}</p>
          </div>
        </div>
      ),
    },
    {
      key: 'role',
      title: '角色',
      width: 110,
      nowrap: true,
      render: (value) => {
        const info = ROLE_LABELS[value] || { label: value, variant: 'default' as const };
        return <Badge variant={info.variant}>{info.label}</Badge>;
      },
    },
    {
      key: 'is_active',
      title: '状态',
      width: 90,
      nowrap: true,
      render: (value) => (
        <Badge variant={value ? 'success' : 'danger'}>
          {value ? '已激活' : '已禁用'}
        </Badge>
      ),
    },
    {
      key: 'created_at',
      title: '注册时间',
      width: 120,
      nowrap: true,
      render: (value) => formatDate(value),
    },
    {
      key: 'actions',
      title: '操作',
      width: 110,
      nowrap: true,
      render: (_, row) => {
        const isSelf = row.id === currentUser?.id;
        return (
          <Button
            size="sm"
            variant={row.is_active ? 'danger' : 'primary'}
            disabled={isSelf}
            onClick={() => handleToggleActive(row.id, row.is_active)}
            title={isSelf ? '不能修改自己的状态' : ''}
          >
            {row.is_active ? (
              <>
                <UserX size={14} className="mr-1" />
                禁用
              </>
            ) : (
              <>
                <UserCheck size={14} className="mr-1" />
                启用
              </>
            )}
          </Button>
        );
      },
    },
  ];

  // 筛选标签
  const filterOptions: Array<{ label: string; value: boolean | undefined }> = [
    { label: '全部', value: undefined },
    { label: '已激活', value: true },
    { label: '已禁用', value: false },
  ];

  return (
    <div className="space-y-4">
      {/* 页面标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-ink">用户管理</h1>
          <p className="text-ink-sub text-sm mt-1">共 {total} 个用户</p>
        </div>
        {/* 筛选 */}
        <div className="flex items-center gap-1 bg-paper border border-line rounded-md p-0.5">
          {filterOptions.map((opt) => (
            <button
              key={String(opt.label)}
              onClick={() => {
                setFilterActive(opt.value);
                setPage(1);
              }}
              className={`px-3 py-1.5 rounded text-sm transition-colors ${
                filterActive === opt.value
                  ? 'bg-lake text-paper'
                  : 'text-ink-sub hover:bg-mist'
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* 批量操作栏 */}
      {selectedKeys.length > 0 && (
        <Card variant="filled" padding="sm">
          <div className="flex items-center justify-between">
            <span className="text-sm text-ink">
              已选择 <span className="font-semibold text-lake">{selectedKeys.length}</span> 个用户
            </span>
            <div className="flex items-center gap-2">
              <Button
                size="sm"
                variant="primary"
                onClick={() => handleBatchToggle(true)}
                loading={batchLoading}
              >
                <UserCheck size={14} className="mr-1" />
                批量启用
              </Button>
              <Button
                size="sm"
                variant="danger"
                onClick={() => handleBatchToggle(false)}
                loading={batchLoading}
              >
                <UserX size={14} className="mr-1" />
                批量禁用
              </Button>
              <Button
                size="sm"
                variant="text"
                onClick={() => setSelectedKeys([])}
              >
                取消选择
              </Button>
            </div>
          </div>
        </Card>
      )}

      {/* 表格 */}
      {users.length === 0 && !loading ? (
        <Card padding="lg" className="text-center py-16">
          <Users size={48} className="mx-auto text-ink-disabled mb-4" />
          <p className="text-ink-sub">暂无用户</p>
        </Card>
      ) : (
        <Table<UserBrief>
          columns={columns}
          data={users}
          loading={loading}
          selectable
          selectedRowKeys={selectedKeys}
          onSelectionChange={setSelectedKeys}
          emptyText="暂无用户"
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

      {/* Toast */}
      {toast && (
        <div className="fixed bottom-6 right-6 z-50">
          <div
            className={`px-4 py-3 rounded-lg shadow-lg text-sm ${
              toast.type === 'success'
                ? 'bg-grass text-paper'
                : toast.type === 'warning'
                ? 'bg-sun text-ink'
                : 'bg-danger text-paper'
            }`}
          >
            {toast.message}
          </div>
        </div>
      )}
    </div>
  );
};

export default AdminUsersPage;

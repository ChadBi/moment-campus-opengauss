import React, { useState, useEffect } from 'react';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Badge } from '../../components/ui/Badge';
import { Avatar } from '../../components/ui/Avatar';
import { Loading } from '../../components/ui/Loading';
import { Toast } from '../../components/ui/Toast';
import { api } from '../../services/api';
import { Users, Check, X } from 'lucide-react';

interface User {
  id: number;
  email: string;
  nickname: string;
  avatar_url?: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

const AdminUsersPage: React.FC = () => {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  useEffect(() => {
    loadUsers();
  }, []);

  const loadUsers = async () => {
    try {
      setLoading(true);
      const response = await api.get('/admin/users');
      setUsers(response.data);
    } catch (error) {
      console.error('加载用户列表失败:', error);
      setToast({ message: '加载用户列表失败', type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const handleToggleActive = async (userId: number, currentStatus: boolean) => {
    const action = currentStatus ? '禁用' : '启用';
    if (!confirm(`确定要${action}该用户吗？`)) return;

    try {
      await api.put(`/admin/users/${userId}/toggle-active`);
      setUsers(users.map(u => 
        u.id === userId ? { ...u, is_active: !currentStatus } : u
      ));
      setToast({ message: `${action}成功`, type: 'success' });
    } catch (error) {
      console.error(`${action}失败:`, error);
      setToast({ message: `${action}失败`, type: 'error' });
    }
  };

  if (loading) {
    return (
      <div className="py-12">
        <Loading text="加载中..." />
      </div>
    );
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-text-main">用户管理</h1>
        <p className="text-text-sub text-sm mt-1">
          共 {users.length} 个用户
        </p>
      </div>

      {users.length === 0 ? (
        <Card padding="lg" className="text-center py-12">
          <Users size={48} className="mx-auto text-text-disabled mb-4" />
          <p className="text-text-sub">暂无用户</p>
        </Card>
      ) : (
        <div className="space-y-4">
          {users.map(user => (
            <Card key={user.id} padding="md">
              <div className="flex items-center gap-4">
                <Avatar
                  src={user.avatar_url}
                  fallback={user.nickname?.[0] || '?'}
                  size="md"
                />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-medium text-text-main">
                      {user.nickname}
                    </span>
                    <Badge 
                      variant={user.role === 'admin' ? 'info' : 'default'} 
                      className="text-xs"
                    >
                      {user.role === 'admin' ? '管理员' : '普通用户'}
                    </Badge>
                    <Badge 
                      variant={user.is_active ? 'success' : 'danger'} 
                      className="text-xs"
                    >
                      {user.is_active ? '已激活' : '已禁用'}
                    </Badge>
                  </div>
                  <p className="text-text-sub text-sm">{user.email}</p>
                  <p className="text-text-sub text-xs mt-1">
                    注册时间：{new Date(user.created_at).toLocaleDateString('zh-CN')}
                  </p>
                </div>
                <Button
                  size="sm"
                  variant={user.is_active ? 'danger' : 'primary'}
                  onClick={() => handleToggleActive(user.id, user.is_active)}
                >
                  {user.is_active ? (
                    <>
                      <X size={16} className="mr-1" />
                      禁用
                    </>
                  ) : (
                    <>
                      <Check size={16} className="mr-1" />
                      启用
                    </>
                  )}
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}

      {toast && (
        <Toast
          message={toast.message}
          type={toast.type}
          onClose={() => setToast(null)}
        />
      )}
    </div>
  );
};

export default AdminUsersPage;

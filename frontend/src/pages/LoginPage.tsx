import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/useAuthStore';
import { authApi } from '../services/auth';
import { Input } from '../components/ui/Input';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { Toast } from '../components/ui/Toast';
import { Mail, Lock, ArrowLeft } from 'lucide-react';

const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const { setAuth } = useAuthStore();
  const [formData, setFormData] = useState({
    email: '',
    password: '',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'warning' | 'info' } | null>(null);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
    setError(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!formData.email || !formData.password) {
      setError('请填写所有必填项');
      return;
    }

    setLoading(true);
    try {
      const response = await authApi.login({ email: formData.email, password: formData.password });
      setAuth(response.user, response.access_token, response.refresh_token);
      setToast({ message: '登录成功', type: 'success' });
      const role = response.user?.role;
      const isAdmin = role === 'admin' || role === 'super_admin';
      navigate(isAdmin ? '/admin' : '/');
    } catch (err: any) {
      const message = err.response?.data?.detail || '登录失败，请检查邮箱和密码';
      setError(message);
      setToast({ message, type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-mist px-4 py-10">
      <div className="w-full max-w-[400px]">
        <div className="flex flex-col items-center mb-7">
          <div className="relative w-[44px] h-[44px] rounded-[12px] bg-paper grid place-items-center shadow-sm overflow-hidden mb-4">
            <span
              className="font-display font-bold text-[22px] text-lake leading-none"
            >
              此
            </span>
          </div>
          <h1 className="font-display font-bold text-[24px] text-lake tracking-wide leading-none">
            欢迎回来
          </h1>
          <p className="text-ink-muted text-sm mt-2">把会消失的校园经验留下来</p>
        </div>

        <Card variant="elevated" padding="lg">
          <form onSubmit={handleSubmit} className="space-y-4">
            <Input
              label="邮箱"
              name="email"
              type="email"
              value={formData.email}
              onChange={handleChange}
              placeholder="请输入邮箱"
              icon={<Mail size={16} />}
              required
            />

            <Input
              label="密码"
              name="password"
              type="password"
              value={formData.password}
              onChange={handleChange}
              placeholder="请输入密码"
              icon={<Lock size={16} />}
              required
            />

            {error && (
              <div className="text-danger text-sm text-center bg-danger/8 rounded-[10px] py-2 px-3">
                {error}
              </div>
            )}

            <Button
              type="submit"
              variant="primary"
              size="lg"
              loading={loading}
              className="w-full"
            >
              登录
            </Button>
          </form>

          <div className="mt-5 text-center text-sm">
            <span className="text-ink-muted">还没有账号？</span>
            <Link to="/register" className="text-lake font-medium ml-1 hover:underline">
              立即注册
            </Link>
          </div>

          <button
            type="button"
            onClick={() => navigate('/')}
            className="mt-4 w-full flex items-center justify-center gap-1.5 text-sm text-ink-muted hover:text-ink transition-colors py-2"
          >
            <ArrowLeft size={14} />
            以访客身份继续浏览
          </button>
        </Card>
      </div>

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

export default LoginPage;

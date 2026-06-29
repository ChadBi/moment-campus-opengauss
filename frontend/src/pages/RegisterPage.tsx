import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/useAuthStore';
import { authApi } from '../services/auth';
import { Input } from '../components/ui/Input';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { Toast } from '../components/ui/Toast';
import { Mail, Lock, User } from 'lucide-react';

const RegisterPage: React.FC = () => {
  const navigate = useNavigate();
  const { setAuth } = useAuthStore();
  const [formData, setFormData] = useState({
    email: '',
    nickname: '',
    password: '',
    confirmPassword: '',
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

    if (!formData.email || !formData.nickname || !formData.password || !formData.confirmPassword) {
      setError('请填写所有必填项');
      return;
    }

    if (formData.password !== formData.confirmPassword) {
      setError('两次输入的密码不一致');
      return;
    }

    if (formData.password.length < 6) {
      setError('密码长度至少为6位');
      return;
    }

    setLoading(true);
    try {
      // 注册并自动登录
      const response = await authApi.register({
        email: formData.email,
        nickname: formData.nickname,
        password: formData.password,
        school_id: 1,
      });
      setAuth(response.user, response.access_token, response.refresh_token);
      setToast({ message: '注册成功', type: 'success' });
      setTimeout(() => navigate('/'), 1000);
    } catch (err: any) {
      const message = err.response?.data?.detail || '注册失败，请稍后重试';
      setError(message);
      setToast({ message, type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-bg-body px-4 py-10 relative overflow-hidden">
      {/* 装饰圆 */}
      <div className="pointer-events-none absolute -top-24 -right-20 w-72 h-72 rounded-full border-[24px] border-mist/60" />
      <div className="pointer-events-none absolute -bottom-28 -left-20 w-80 h-80 rounded-full border-[28px] border-mist/60" />

      <div className="w-full max-w-md relative">
        {/* 品牌标志 */}
        <div className="flex flex-col items-center mb-7">
          <div className="relative w-[68px] h-[68px] rounded-[22px] bg-paper grid place-items-center shadow-md mb-4 overflow-hidden">
            <span className="font-display font-bold text-[34px] text-lake leading-none translate-y-[-2px]">此</span>
            <span className="absolute top-[34px] left-[16px] w-[36px] h-[12px] border-t-[3px] border-lamp rounded-full rotate-[-12deg]" />
          </div>
          <span className="eyebrow mb-2">JOIN CAMPUS</span>
          <h1 className="text-2xl font-display font-bold text-lake">加入此刻校园</h1>
          <p className="text-ink-sub text-sm mt-1.5">分享你的校园生活每一刻</p>
        </div>

        {/* 表单卡片 */}
        <Card variant="elevated" padding="lg">
          <form onSubmit={handleSubmit} className="space-y-5">
            <Input
              label="邮箱"
              name="email"
              type="email"
              value={formData.email}
              onChange={handleChange}
              placeholder="请输入邮箱"
              icon={<Mail size={18} />}
              required
            />

            <Input
              label="昵称"
              name="nickname"
              type="text"
              value={formData.nickname}
              onChange={handleChange}
              placeholder="请输入昵称"
              icon={<User size={18} />}
              required
            />

            <Input
              label="密码"
              name="password"
              type="password"
              value={formData.password}
              onChange={handleChange}
              placeholder="请输入密码（至少6位）"
              icon={<Lock size={18} />}
              required
            />

            <Input
              label="确认密码"
              name="confirmPassword"
              type="password"
              value={formData.confirmPassword}
              onChange={handleChange}
              placeholder="请再次输入密码"
              icon={<Lock size={18} />}
              required
            />

            {error && (
              <div className="text-danger text-sm text-center bg-danger/8 rounded-md py-2 px-3">
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
              注册
            </Button>
          </form>

          <div className="mt-6 text-center text-sm">
            <span className="text-ink-sub">已有账号？</span>
            <Link to="/login" className="text-lamp font-medium ml-1 hover:underline">
              立即登录
            </Link>
          </div>
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

export default RegisterPage;

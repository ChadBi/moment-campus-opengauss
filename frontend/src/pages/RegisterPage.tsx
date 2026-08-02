import React, { useState, useEffect } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useAuthStore } from '../store/useAuthStore';
import { useCampusStore } from '../store/useCampusStore';
import { authApi } from '../services/auth';
import { schoolsApi } from '../services/schools';
import { Input } from '../components/ui/Input';
import { Button } from '../components/ui/Button';
import { Card } from '../components/ui/Card';
import { Toast } from '../components/ui/Toast';
import { Mail, Lock, User, School as SchoolIcon, ChevronDown } from 'lucide-react';

const RegisterPage: React.FC = () => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { setAuth } = useAuthStore();
  const { schools, setSchools, setCurrentSchool } = useCampusStore();
  const [formData, setFormData] = useState({
    email: '',
    nickname: '',
    password: '',
    confirmPassword: '',
    schoolId: '' as number | '',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'warning' | 'info' } | null>(null);

  // ACC-01.1: 读取注册后回跳目标
  const redirectTo = searchParams.get('redirect') || '/';

  // 2026-08-01：注册时自由选择初始加入的学校（从公开目录拉取，供下拉选择）
  useEffect(() => {
    if (schools.length > 0) return;
    let cancelled = false;
    (async () => {
      try {
        const list = await schoolsApi.listSchools();
        if (!cancelled) setSchools(list);
      } catch {
        // 拉取失败不阻塞注册流程（用户仍可进入，仅无学校可选）
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [schools.length, setSchools]);

  const selectedSchool = schools.find((s) => s.id === formData.schoolId) ?? null;

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: name === 'schoolId' ? (value ? Number(value) : '') : value,
    }));
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

    // 2026-08-01：注册时用户显式选择初始加入的学校（不再默认绑定某所学校）
    if (typeof formData.schoolId !== 'number') {
      setError('请选择要加入的学校');
      return;
    }

    setLoading(true);
    try {
      const response = await authApi.register({
        email: formData.email,
        nickname: formData.nickname,
        password: formData.password,
        school_id: formData.schoolId,
      });
      setAuth(response.user, response.access_token, response.refresh_token);
      setToast({ message: '注册成功', type: 'success' });

      // 2026-08-02：注册成功后同步当前学校为注册选择的学校，
      // 避免 store 持久化/URL 残留其他学校（游客态浏览过的）触发
      // "您没有该学校的访问权限，已切换回 xxx" 回退提示
      const targetSchool = schools.find((s) => s.id === formData.schoolId);
      if (targetSchool) {
        setCurrentSchool(targetSchool);
        // 立即同步改写 URL 中的 school 参数（与 store 同一批次）。
        // 若延迟到跳转时才改写，useSchoolSync 的 URL 监听器会先读到
        // 残留的旧学校值（如 ?school=fudan），反向覆盖刚设置的当前学校，
        // 最终由 ensureValidSchool 回退并弹出"无访问权限"提示。
        const next = new URLSearchParams(searchParams);
        next.set('school', targetSchool.code);
        setSearchParams(next, { replace: true });
      }

      // ACC-01.1: 注册后回跳到原目标页；重写 URL 中的 school 参数为注册学校，
      // 保证跳转后学校上下文与 membership 一致（无权限回退不再触发）
      const [path, queryStr = ''] = redirectTo.split('?');
      const params = new URLSearchParams(queryStr);
      if (targetSchool) {
        params.set('school', targetSchool.code);
      } else {
        params.delete('school');
      }
      const qs = params.toString();
      const targetUrl = qs ? `${path}?${qs}` : path;
      setTimeout(() => navigate(targetUrl), 1000);
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      const message = e?.response?.data?.detail || '注册失败，请稍后重试';
      setError(message);
      setToast({ message, type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-mist px-4 py-10">
      <div className="w-full max-w-md">
        <div className="flex flex-col items-center mb-7">
          <div className="relative w-[44px] h-[44px] rounded-[12px] bg-paper grid place-items-center shadow-sm mb-4 overflow-hidden">
            <span className="font-display font-bold text-[22px] text-lake leading-none">此</span>
          </div>
          <h1 className="text-xl font-display font-bold text-lake tracking-wide">加入此刻校园</h1>
          <p className="text-ink-muted text-sm mt-1.5">分享你的校园生活每一刻</p>
        </div>

        <Card variant="elevated" padding="lg">
          {/* 2026-08-01：显示用户选择的初始加入学校 */}
          {selectedSchool && (
            <div className="mb-4 flex items-center gap-2 px-3 py-2 rounded-[10px] bg-lake/5 border border-lake/20">
              <SchoolIcon size={14} className="text-lake flex-shrink-0" />
              <span className="text-sm text-ink">
                将加入：<span className="font-medium">{selectedSchool.name}</span>
              </span>
            </div>
          )}

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
              label="昵称"
              name="nickname"
              type="text"
              value={formData.nickname}
              onChange={handleChange}
              placeholder="请输入昵称"
              icon={<User size={16} />}
              required
            />

            <Input
              label="密码"
              name="password"
              type="password"
              value={formData.password}
              onChange={handleChange}
              placeholder="请输入密码（至少6位）"
              icon={<Lock size={16} />}
              required
            />

            <Input
              label="确认密码"
              name="confirmPassword"
              type="password"
              value={formData.confirmPassword}
              onChange={handleChange}
              placeholder="请再次输入密码"
              icon={<Lock size={16} />}
              required
            />

            {/* 2026-08-01：注册时选择初始加入的学校（公开目录下拉） */}
            <div className="w-full">
              <label
                htmlFor="register-school"
                className="block text-sm font-medium text-ink mb-1.5 font-sans"
              >
                选择加入的学校
                <span className="text-danger ml-1" aria-hidden="true">*</span>
              </label>
              <div className="relative">
                <div className="absolute left-3.5 top-1/2 -translate-y-1/2 text-ink-muted pointer-events-none" aria-hidden="true">
                  <SchoolIcon size={16} />
                </div>
                <select
                  id="register-school"
                  name="schoolId"
                  value={formData.schoolId}
                  onChange={handleChange}
                  required
                  className={`w-full h-10 pl-10 pr-9 bg-paper border rounded-[10px] text-[14px] text-ink appearance-none transition-[background-color,border-color,box-shadow] duration-200 ease-[cubic-bezier(0.16,1,0.3,1)] focus:outline-none focus:border-lake ${
                    error ? 'border-danger focus:border-danger' : 'border-line'
                  } ${formData.schoolId === '' ? 'text-ink-muted/60' : ''}`}
                >
                  <option value="" disabled>
                    {schools.length > 0 ? '请选择学校' : '暂无可选学校'}
                  </option>
                  {schools.map((s) => (
                    <option key={s.id} value={s.id} className="text-ink">
                      {s.name}
                    </option>
                  ))}
                </select>
                <div className="absolute right-3 top-1/2 -translate-y-1/2 text-ink-muted pointer-events-none" aria-hidden="true">
                  <ChevronDown size={16} />
                </div>
              </div>
            </div>

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
              注册
            </Button>
          </form>

          <div className="mt-5 text-center text-sm">
            <span className="text-ink-muted">已有账号？</span>
            <Link to="/login" className="text-lake font-medium ml-1 hover:underline">
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

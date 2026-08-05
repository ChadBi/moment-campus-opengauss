import React, { useEffect, useState } from 'react';
import { BadgeCheck, Shield, Link as LinkIcon, Copy, Check } from 'lucide-react';
import { useAuthStore } from '../store/useAuthStore';
import { usersApi } from '../services/users';
import { Card } from './ui/Card';
import { Button } from './ui/Button';
import { VerifiedBadge } from './VerifiedBadge';
import { Toast } from './ui/Toast';

type ToastState = {
  message: string;
  type: 'success' | 'error' | 'warning' | 'info';
} | null;

/**
 * B-01: 校园身份认证卡片（个人中心）。
 * 未认证：填写学号 + 校园邮箱 → 发送验证（本地环境响应携带 code / verify_link）→ 确认。
 * 已认证：展示「已认证」徽标与说明。
 * UC-01：从验证链接落地页（/verify-campus?token=）带来的 token 自动填入确认框。
 */
export const CampusVerifyCard: React.FC = () => {
  const { user, updateUser } = useAuthStore();
  const campusVerified = Boolean(user?.campus_verified);

  const [step, setStep] = useState<'form' | 'code'>('form');
  const [studentId, setStudentId] = useState('');
  const [campusEmail, setCampusEmail] = useState('');
  const [code, setCode] = useState('');
  const [devCode, setDevCode] = useState<string | null>(null);
  const [verifyLink, setVerifyLink] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState<ToastState>(null);

  // UC-01: 从验证链接落地页带过来的 token（sessionStorage）
  useEffect(() => {
    void Promise.resolve().then(() => {
      const pending = sessionStorage.getItem('pending_verify_token');
      if (pending) {
        sessionStorage.removeItem('pending_verify_token');
        setCode(pending);
        setStep('code');
      }
    });
  }, []);

  const handleSend = async () => {
    if (!studentId.trim() || !campusEmail.trim()) {
      setToast({ message: '请填写学号与校园邮箱', type: 'error' });
      return;
    }
    setLoading(true);
    try {
      const res = await usersApi.sendCampusVerify({
        student_id: studentId.trim(),
        campus_email: campusEmail.trim(),
      });
      setDevCode(res.code ?? null);
      setVerifyLink(res.verify_link ?? null);
      setStep('code');
      setToast({ message: res.message, type: 'success' });
    } catch (error) {
      const e = error as { response?: { data?: { detail?: string } } };
      setToast({ message: e?.response?.data?.detail || '发送失败，请重试', type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const handleConfirm = async () => {
    const credential = code.trim();
    if (!credential) {
      setToast({ message: '请输入验证凭证（验证链接中的 token 或验证码）', type: 'error' });
      return;
    }
    setLoading(true);
    try {
      await usersApi.confirmCampusVerify({
        student_id: studentId.trim(),
        campus_email: campusEmail.trim(),
        code: credential,
      });
      updateUser({ campus_verified: true });
      setToast({ message: '校园身份认证成功', type: 'success' });
    } catch (error) {
      const e = error as { response?: { data?: { detail?: string } } };
      setToast({ message: e?.response?.data?.detail || '认证失败，请重试', type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const handleCopyLink = async () => {
    if (!verifyLink) return;
    try {
      await navigator.clipboard.writeText(verifyLink);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      setToast({ message: '复制失败，请手动选择复制', type: 'error' });
    }
  };

  return (
    <Card variant="elevated" padding="lg" className="mb-4">
      <div className="flex items-center justify-between mb-3">
        <h2 className="font-display font-semibold text-ink flex items-center gap-2">
          <Shield size={18} className="text-lake" />
          校园身份认证
        </h2>
        {campusVerified && <VerifiedBadge />}
      </div>

      {campusVerified ? (
        <div className="flex items-start gap-3 p-3 rounded-[10px] bg-grass/5 border border-grass/20">
          <BadgeCheck size={18} className="text-grass flex-shrink-0 mt-0.5" />
          <div className="text-sm">
            <p className="text-ink font-medium">你已完成校园身份认证</p>
            <p className="text-[11px] text-ink-muted mt-1 leading-relaxed">
              昵称旁会显示「已认证」徽标，帮助同学识别你的信息更可信。
            </p>
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          <p className="text-[12px] text-ink-muted leading-relaxed">
            通过学号 + 校园邮箱验证身份，昵称旁将显示「已认证」徽标，让同学更信任你的信息。
            请使用所在学校的官方邮箱。
          </p>

          {step === 'form' ? (
            <>
              <label className="block">
                <span className="text-xs text-ink-sub">学号</span>
                <input
                  type="text"
                  value={studentId}
                  onChange={(e) => setStudentId(e.target.value)}
                  maxLength={50}
                  placeholder="请输入校园学号"
                  className="mt-1 w-full px-3 py-2 rounded-[10px] border border-line/60 focus:border-lake focus:outline-none text-sm"
                />
              </label>
              <label className="block">
                <span className="text-xs text-ink-sub">校园邮箱</span>
                <input
                  type="email"
                  value={campusEmail}
                  onChange={(e) => setCampusEmail(e.target.value)}
                  maxLength={255}
                  placeholder="name@学校官方域名"
                  className="mt-1 w-full px-3 py-2 rounded-[10px] border border-line/60 focus:border-lake focus:outline-none text-sm"
                />
              </label>
              <Button
                variant="primary"
                disabled={loading}
                onClick={handleSend}
                icon={<Shield size={14} />}
              >
                {loading ? '发送中...' : '发送验证码'}
              </Button>
            </>
          ) : (
            <>
              <label className="block">
                <span className="text-xs text-ink-sub">验证凭证（token 或验证码）</span>
                <input
                  type="text"
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  maxLength={128}
                  placeholder="粘贴验证链接中的 token 或验证码"
                  className="mt-1 w-full px-3 py-2 rounded-[10px] border border-line/60 focus:border-lake focus:outline-none text-sm"
                />
              </label>
              {verifyLink && (
                <div className="rounded-[8px] bg-lake/5 border border-lake/20 px-3 py-2 text-xs text-lake">
                  <div className="flex items-center gap-2">
                    <LinkIcon size={12} />
                    <span className="font-medium">验证链接：</span>
                    <button
                      type="button"
                      onClick={handleCopyLink}
                      className="inline-flex items-center gap-1 text-lake font-medium hover:underline"
                    >
                      {copied ? <Check size={12} /> : <Copy size={12} />}
                      {copied ? '已复制' : '复制链接'}
                    </button>
                  </div>
                  <span className="block text-[10px] text-ink-muted mt-1 break-all">
                    正式环境该链接将发送至你的校园邮箱
                  </span>
                </div>
              )}
              {devCode && (
                <div className="rounded-[8px] bg-lake/5 border border-lake/20 px-3 py-2 text-xs text-lake">
                  👇 演示环境验证凭证：
                  <span className="font-data font-bold tracking-wide break-all">{devCode}</span>
                  <span className="block text-[10px] text-ink-muted mt-0.5">
                    直接复制到上方输入框即可完成认证
                  </span>
                </div>
              )}
              <div className="flex items-center gap-2">
                <Button
                  variant="primary"
                  disabled={loading}
                  onClick={handleConfirm}
                  icon={<BadgeCheck size={14} />}
                >
                  {loading ? '确认中...' : '确认认证'}
                </Button>
                <Button
                  variant="text"
                  disabled={loading}
                  onClick={() => setStep('form')}
                >
                  返回修改
                </Button>
              </div>
            </>
          )}
        </div>
      )}

      {toast && (
        <Toast
          message={toast.message}
          type={toast.type}
          onClose={() => setToast(null)}
        />
      )}
    </Card>
  );
};
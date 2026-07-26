import React, { useCallback, useEffect, useState } from 'react';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { Badge } from '../../components/ui/Badge';
import { Loading } from '../../components/ui/Loading';
import { adminApi, type SchoolSettings } from '../../services/admin';
import { useUIStore } from '../../store/useUIStore';
import { Settings, Save, Cloud, Info, RotateCcw } from 'lucide-react';

/**
 * ADM-02.1: 校级系统设置页（后端真实存储，跨浏览器生效）
 *
 * - 设置存于 school_settings 表，由 TenantContext 决定 school_id
 * - admin/super_admin 可读可写；普通 user 403（路由守卫已拦截）
 * - 修改后端记录审计日志（old/new/operator），前端不参与存储
 */
const AdminSettingsPage: React.FC = () => {
  const showToast = useUIStore((s) => s.showToast);

  const [settings, setSettings] = useState<SchoolSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  // 表单字段（独立维护，便于部分更新与比对）
  const [siteName, setSiteName] = useState('');
  const [description, setDescription] = useState('');
  const [requireReview, setRequireReview] = useState(true);
  const [allowAnonymous, setAllowAnonymous] = useState(true);
  const [allowComments, setAllowComments] = useState(true);
  const [publishFrequency, setPublishFrequency] = useState(10);
  const [imageLimit, setImageLimit] = useState(9);
  const [defaultValidityDays, setDefaultValidityDays] = useState(30);
  const [brandColor, setBrandColor] = useState('');
  const [logoUrl, setLogoUrl] = useState('');

  /** 从后端加载设置并同步到表单状态 */
  const loadSettings = useCallback(async () => {
    setLoading(true);
    try {
      const data = await adminApi.getSchoolSettings();
      setSettings(data);
      setSiteName(data.site_name ?? '');
      setDescription(data.description ?? '');
      setRequireReview(data.require_review);
      setAllowAnonymous(data.allow_anonymous);
      setAllowComments(data.allow_comments);
      setPublishFrequency(data.publish_frequency);
      setImageLimit(data.image_limit);
      setDefaultValidityDays(data.default_validity_days);
      setBrandColor(data.brand_color ?? '');
      setLogoUrl(data.logo_url ?? '');
    } catch (error) {
      console.error('加载学校设置失败:', error);
      showToast('加载学校设置失败，请稍后重试', 'error');
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  useEffect(() => {
    void loadSettings();
  }, [loadSettings]);

  /** 校验数值范围（与后端 Pydantic 约束一致） */
  const validate = (): string | null => {
    if (!siteName.trim() && siteName.length > 100) {
      return '站点名称不能超过 100 个字符';
    }
    if (publishFrequency < 0 || publishFrequency > 1000) {
      return '每日发布上限需在 0~1000 之间';
    }
    if (imageLimit < 0 || imageLimit > 20) {
      return '单帖图片上限需在 0~20 之间';
    }
    if (defaultValidityDays < 1 || defaultValidityDays > 3650) {
      return '默认有效期天数需在 1~3650 之间';
    }
    if (brandColor && brandColor.length > 20) {
      return '品牌色长度不能超过 20';
    }
    if (logoUrl && logoUrl.length > 500) {
      return 'Logo URL 长度不能超过 500';
    }
    return null;
  };

  /** 收集表单中相对原始值发生变化的字段（部分更新） */
  const buildPayload = (): Record<string, unknown> => {
    if (!settings) return {};
    const payload: Record<string, unknown> = {};

    // 文本字段：空字符串统一转为 null（与后端 Optional[str] 对齐）
    const nextSiteName = siteName.trim() || null;
    if ((settings.site_name ?? null) !== nextSiteName) {
      payload.site_name = nextSiteName;
    }
    const nextDescription = description.trim() || null;
    if ((settings.description ?? null) !== nextDescription) {
      payload.description = nextDescription;
    }
    if (settings.require_review !== requireReview) {
      payload.require_review = requireReview;
    }
    if (settings.allow_anonymous !== allowAnonymous) {
      payload.allow_anonymous = allowAnonymous;
    }
    if (settings.allow_comments !== allowComments) {
      payload.allow_comments = allowComments;
    }
    if (settings.publish_frequency !== publishFrequency) {
      payload.publish_frequency = publishFrequency;
    }
    if (settings.image_limit !== imageLimit) {
      payload.image_limit = imageLimit;
    }
    if (settings.default_validity_days !== defaultValidityDays) {
      payload.default_validity_days = defaultValidityDays;
    }
    const nextBrandColor = brandColor.trim() || null;
    if ((settings.brand_color ?? null) !== nextBrandColor) {
      payload.brand_color = nextBrandColor;
    }
    const nextLogoUrl = logoUrl.trim() || null;
    if ((settings.logo_url ?? null) !== nextLogoUrl) {
      payload.logo_url = nextLogoUrl;
    }
    return payload;
  };

  const handleSave = async () => {
    const err = validate();
    if (err) {
      showToast(err, 'error');
      return;
    }
    const payload = buildPayload();
    if (Object.keys(payload).length === 0) {
      showToast('未检测到变更，无需保存', 'info');
      return;
    }

    setSaving(true);
    try {
      const updated = await adminApi.updateSchoolSettings(payload);
      setSettings(updated);
      // 同步表单为后端权威值
      setSiteName(updated.site_name ?? '');
      setDescription(updated.description ?? '');
      setRequireReview(updated.require_review);
      setAllowAnonymous(updated.allow_anonymous);
      setAllowComments(updated.allow_comments);
      setPublishFrequency(updated.publish_frequency);
      setImageLimit(updated.image_limit);
      setDefaultValidityDays(updated.default_validity_days);
      setBrandColor(updated.brand_color ?? '');
      setLogoUrl(updated.logo_url ?? '');
      showToast('设置已保存（全校生效）', 'success');
    } catch (error) {
      console.error('保存学校设置失败:', error);
      showToast('保存失败，请检查网络或权限后重试', 'error');
    } finally {
      setSaving(false);
    }
  };

  /** 重置为最近一次从后端拉取的值（不写后端） */
  const handleReset = () => {
    if (!settings) return;
    if (!window.confirm('确定放弃当前未保存的修改吗？')) return;
    setSiteName(settings.site_name ?? '');
    setDescription(settings.description ?? '');
    setRequireReview(settings.require_review);
    setAllowAnonymous(settings.allow_anonymous);
    setAllowComments(settings.allow_comments);
    setPublishFrequency(settings.publish_frequency);
    setImageLimit(settings.image_limit);
    setDefaultValidityDays(settings.default_validity_days);
    setBrandColor(settings.brand_color ?? '');
    setLogoUrl(settings.logo_url ?? '');
    showToast('已恢复到最近一次保存值', 'info');
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loading />
      </div>
    );
  }

  const updatedAtText = settings
    ? new Date(settings.updated_at).toLocaleString('zh-CN', {
        hour12: false,
      })
    : '—';

  return (
    <div className="space-y-4">
      {/* 页面标题 */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-ink">系统设置</h1>
          <p className="text-ink-sub text-sm mt-1">管理本校系统配置</p>
        </div>
        <Badge variant="success">
          <Cloud size={12} className="mr-1" />
          后端存储·跨浏览器生效
        </Badge>
      </div>

      {/* 说明条 */}
      <Card variant="filled" padding="sm">
        <div className="flex items-start gap-2 text-sm text-ink-sub">
          <Info size={16} className="text-info flex-shrink-0 mt-0.5" />
          <p>
            设置存于后端 <code className="px-1 py-0.5 bg-paper rounded text-xs">school_settings</code> 表，
            对全校所有浏览器立即生效。修改将记录审计日志（旧值/新值/操作者）。
            学校身份由 TenantContext 决定，无法在请求中篡改。
          </p>
        </div>
      </Card>

      {/* 基本设置 */}
      <Card variant="outlined" padding="md">
        <h2 className="text-lg font-semibold text-ink mb-4 flex items-center gap-2">
          <Settings size={20} />
          基本设置
        </h2>
        <div className="space-y-4">
          <Input
            label="站点名称"
            value={siteName}
            onChange={(e) => setSiteName(e.target.value)}
            placeholder="如：此刻校园·江南"
            maxLength={100}
          />
          <div className="w-full">
            <label className="block text-sm font-medium text-ink mb-1.5 font-sans">
              站点说明
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="简要描述本站点定位与用途"
              rows={3}
              className="w-full px-3.5 py-2.5 bg-paper border border-line rounded-[10px] text-[14px] text-ink placeholder:text-ink-muted/60 transition-[background-color,border-color,box-shadow] duration-200 ease-[cubic-bezier(0.16,1,0.3,1)] focus:outline-none focus:border-lake resize-none"
            />
          </div>
        </div>
      </Card>

      {/* 品牌设置 */}
      <Card variant="outlined" padding="md">
        <h2 className="text-lg font-semibold text-ink mb-4">品牌设置</h2>
        <div className="space-y-4">
          <Input
            label="品牌色"
            value={brandColor}
            onChange={(e) => setBrandColor(e.target.value)}
            placeholder="如：#1890ff"
            maxLength={20}
          />
          {brandColor && (
            <div className="flex items-center gap-2 text-sm text-ink-sub">
              <span>预览：</span>
              <span
                className="inline-block w-6 h-6 rounded border border-line"
                style={{ backgroundColor: brandColor }}
              />
              <span className="font-mono">{brandColor}</span>
            </div>
          )}
          <Input
            label="Logo URL"
            value={logoUrl}
            onChange={(e) => setLogoUrl(e.target.value)}
            placeholder="https://..."
            maxLength={500}
          />
        </div>
      </Card>

      {/* 内容限制 */}
      <Card variant="outlined" padding="md">
        <h2 className="text-lg font-semibold text-ink mb-4">内容限制</h2>
        <div className="space-y-4">
          <Input
            label="每日发布上限（0 表示不限）"
            type="number"
            min={0}
            max={1000}
            value={publishFrequency.toString()}
            onChange={(e) =>
              setPublishFrequency(parseInt(e.target.value, 10) || 0)
            }
          />
          <Input
            label="单帖图片上限"
            type="number"
            min={0}
            max={20}
            value={imageLimit.toString()}
            onChange={(e) => setImageLimit(parseInt(e.target.value, 10) || 0)}
          />
          <Input
            label="默认有效期天数"
            type="number"
            min={1}
            max={3650}
            value={defaultValidityDays.toString()}
            onChange={(e) =>
              setDefaultValidityDays(parseInt(e.target.value, 10) || 1)
            }
          />
        </div>
      </Card>

      {/* 功能开关 */}
      <Card variant="outlined" padding="md">
        <h2 className="text-lg font-semibold text-ink mb-4">功能开关</h2>
        <div className="space-y-3">
          {[
            {
              key: 'requireReview' as const,
              label: '新信息需要审核',
              desc: '开启后用户发布的信息需管理员审核才可见',
              value: requireReview,
              setter: setRequireReview,
            },
            {
              key: 'allowComments' as const,
              label: '允许评论',
              desc: '允许用户对信息进行评论',
              value: allowComments,
              setter: setAllowComments,
            },
            {
              key: 'allowAnonymous' as const,
              label: '允许匿名发布',
              desc: '用户可选择匿名身份发布信息',
              value: allowAnonymous,
              setter: setAllowAnonymous,
            },
          ].map((item) => (
            <label
              key={item.key}
              className="flex items-start gap-3 p-3 rounded-md border border-line bg-paper hover:bg-mist/40 cursor-pointer transition-colors"
            >
              <input
                type="checkbox"
                checked={item.value}
                onChange={(e) => item.setter(e.target.checked)}
                className="w-4 h-4 mt-0.5 rounded border-line text-lake focus:ring-lake/30 cursor-pointer"
              />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-ink">{item.label}</p>
                <p className="text-xs text-ink-muted mt-0.5">{item.desc}</p>
              </div>
              <Badge variant={item.value ? 'success' : 'default'}>
                {item.value ? '已开启' : '已关闭'}
              </Badge>
            </label>
          ))}
        </div>
      </Card>

      {/* 操作按钮 */}
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs text-ink-muted">
          最近更新：{updatedAtText}
        </p>
        <div className="flex items-center gap-2">
          <Button
            variant="text"
            onClick={handleReset}
            icon={<RotateCcw size={14} />}
          >
            放弃修改
          </Button>
          <Button
            variant="primary"
            onClick={handleSave}
            loading={saving}
            icon={<Save size={16} />}
          >
            保存设置
          </Button>
        </div>
      </div>
    </div>
  );
};

export default AdminSettingsPage;

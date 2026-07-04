import React, { useState, useEffect } from 'react';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { Badge } from '../../components/ui/Badge';
import { Settings, Save, Database, Info } from 'lucide-react';

/** 本地配置 Schema */
interface LocalSettings {
  site_name: string;
  site_description: string;
  max_posts_per_user: number;
  max_images_per_post: number;
  require_approval: boolean;
  enable_comments: boolean;
  enable_anonymous: boolean;
}

const STORAGE_KEY = 'moment_campus_admin_settings';

const DEFAULT_SETTINGS: LocalSettings = {
  site_name: '此刻校园',
  site_description: '校园生活信息平台',
  max_posts_per_user: 50,
  max_images_per_post: 9,
  require_approval: true,
  enable_comments: true,
  enable_anonymous: true,
};

/** 从 localStorage 加载配置 */
const loadSettings = (): LocalSettings => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_SETTINGS;
    const parsed = JSON.parse(raw);
    // 合并默认值，防止旧版本缺字段
    return { ...DEFAULT_SETTINGS, ...parsed };
  } catch {
    return DEFAULT_SETTINGS;
  }
};

const AdminSettingsPage: React.FC = () => {
  const [settings, setSettings] = useState<LocalSettings>(DEFAULT_SETTINGS);
  const [loaded, setLoaded] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);
  const [saving, setSaving] = useState(false);

  // 加载本地配置
  useEffect(() => {
    setSettings(loadSettings());
    setLoaded(true);
  }, []);

  /** 保存到 localStorage */
  const handleSave = () => {
    setSaving(true);
    try {
      // 简单校验
      if (!settings.site_name.trim()) {
        setToast({ message: '站点名称不能为空', type: 'error' });
        setSaving(false);
        return;
      }
      if (settings.max_posts_per_user < 0 || settings.max_images_per_post < 0) {
        setToast({ message: '数值限制不能为负数', type: 'error' });
        setSaving(false);
        return;
      }
      localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
      setToast({ message: '设置已保存（仅本浏览器生效）', type: 'success' });
    } catch (error) {
      console.error('保存设置失败:', error);
      setToast({ message: '保存失败，请检查浏览器存储权限', type: 'error' });
    } finally {
      setSaving(false);
    }
  };

  /** 恢复默认 */
  const handleReset = () => {
    if (!window.confirm('确定恢复所有设置为默认值吗？')) return;
    setSettings(DEFAULT_SETTINGS);
    localStorage.removeItem(STORAGE_KEY);
    setToast({ message: '已恢复默认设置（未保存）', type: 'success' });
  };

  if (!loaded) {
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
    <div className="space-y-4">
      {/* 页面标题 */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-ink">系统设置</h1>
          <p className="text-ink-sub text-sm mt-1">管理系统配置</p>
        </div>
        <Badge variant="warning">
          <Database size={12} className="mr-1" />
          前端本地配置
        </Badge>
      </div>

      {/* 说明条 */}
      <Card variant="filled" padding="sm">
        <div className="flex items-start gap-2 text-sm text-ink-sub">
          <Info size={16} className="text-info flex-shrink-0 mt-0.5" />
          <p>
            当前设置为浏览器本地配置，仅影响本机展示与校验逻辑，不会同步到后端。
            如需全局生效，请联系开发人员将其迁移至后端配置表。
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
            value={settings.site_name}
            onChange={(e) => setSettings({ ...settings, site_name: e.target.value })}
          />
          <Input
            label="站点描述"
            value={settings.site_description}
            onChange={(e) => setSettings({ ...settings, site_description: e.target.value })}
          />
        </div>
      </Card>

      {/* 内容限制 */}
      <Card variant="outlined" padding="md">
        <h2 className="text-lg font-semibold text-ink mb-4">内容限制</h2>
        <div className="space-y-4">
          <Input
            label="每用户最大信息数"
            type="number"
            value={settings.max_posts_per_user.toString()}
            onChange={(e) =>
              setSettings({
                ...settings,
                max_posts_per_user: parseInt(e.target.value) || 0,
              })
            }
          />
          <Input
            label="每条信息最大图片数"
            type="number"
            value={settings.max_images_per_post.toString()}
            onChange={(e) =>
              setSettings({
                ...settings,
                max_images_per_post: parseInt(e.target.value) || 0,
              })
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
              key: 'require_approval' as const,
              label: '新信息需要审核',
              desc: '开启后用户发布的信息需管理员审核才可见',
            },
            {
              key: 'enable_comments' as const,
              label: '启用评论功能',
              desc: '允许用户对信息进行评论',
            },
            {
              key: 'enable_anonymous' as const,
              label: '允许匿名发布',
              desc: '用户可选择匿名身份发布信息',
            },
          ].map((item) => (
            <label
              key={item.key}
              className="flex items-start gap-3 p-3 rounded-md border border-line bg-paper hover:bg-mist/40 cursor-pointer transition-colors"
            >
              <input
                type="checkbox"
                checked={settings[item.key]}
                onChange={(e) =>
                  setSettings({ ...settings, [item.key]: e.target.checked })
                }
                className="w-4 h-4 mt-0.5 rounded border-line text-lake focus:ring-lake/30 cursor-pointer"
              />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-ink">{item.label}</p>
                <p className="text-xs text-ink-muted mt-0.5">{item.desc}</p>
              </div>
              <Badge variant={settings[item.key] ? 'success' : 'default'}>
                {settings[item.key] ? '已开启' : '已关闭'}
              </Badge>
            </label>
          ))}
        </div>
      </Card>

      {/* 操作按钮 */}
      <div className="flex items-center justify-end gap-2">
        <Button variant="text" onClick={handleReset}>
          恢复默认
        </Button>
        <Button variant="primary" onClick={handleSave} loading={saving}>
          <Save size={16} className="mr-2" />
          保存设置
        </Button>
      </div>

      {/* Toast */}
      {toast && (
        <div className="fixed bottom-6 right-6 z-50">
          <div
            className={`px-4 py-3 rounded-lg shadow-lg text-sm ${
              toast.type === 'success' ? 'bg-grass text-paper' : 'bg-danger text-paper'
            }`}
          >
            {toast.message}
          </div>
        </div>
      )}
    </div>
  );
};

export default AdminSettingsPage;

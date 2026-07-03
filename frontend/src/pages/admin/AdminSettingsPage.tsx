import React, { useState } from 'react';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';
import { Toast } from '../../components/ui/Toast';
import { Settings, Save } from 'lucide-react';

const AdminSettingsPage: React.FC = () => {
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);
  const [settings, setSettings] = useState({
    site_name: '此刻校园',
    site_description: '校园生活信息平台',
    max_posts_per_user: 50,
    max_images_per_post: 9,
    require_approval: true,
    enable_comments: true,
    enable_anonymous: true,
  });

  const handleSave = () => {
    // TODO: 实现保存设置逻辑
    console.log('保存设置:', settings);
    setToast({ message: '设置已保存', type: 'success' });
  };

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-ink">系统设置</h1>
        <p className="text-ink-sub text-sm mt-1">管理系统配置</p>
      </div>

      <div className="space-y-6">
        <Card padding="md">
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

        <Card padding="md">
          <h2 className="text-lg font-semibold text-ink mb-4">
            内容限制
          </h2>
          <div className="space-y-4">
            <Input
              label="每用户最大信息数"
              type="number"
              value={settings.max_posts_per_user.toString()}
              onChange={(e) => setSettings({ 
                ...settings, 
                max_posts_per_user: parseInt(e.target.value) || 0 
              })}
            />
            <Input
              label="每条信息最大图片数"
              type="number"
              value={settings.max_images_per_post.toString()}
              onChange={(e) => setSettings({ 
                ...settings, 
                max_images_per_post: parseInt(e.target.value) || 0 
              })}
            />
          </div>
        </Card>

        <Card padding="md">
          <h2 className="text-lg font-semibold text-ink mb-4">
            功能开关
          </h2>
          <div className="space-y-4">
            <label className="flex items-center gap-3">
              <input
                type="checkbox"
                checked={settings.require_approval}
                onChange={(e) => setSettings({ 
                  ...settings, 
                  require_approval: e.target.checked 
                })}
                className="w-4 h-4"
              />
              <span className="text-ink">新信息需要审核</span>
            </label>
            <label className="flex items-center gap-3">
              <input
                type="checkbox"
                checked={settings.enable_comments}
                onChange={(e) => setSettings({ 
                  ...settings, 
                  enable_comments: e.target.checked 
                })}
                className="w-4 h-4"
              />
              <span className="text-ink">启用评论功能</span>
            </label>
            <label className="flex items-center gap-3">
              <input
                type="checkbox"
                checked={settings.enable_anonymous}
                onChange={(e) => setSettings({ 
                  ...settings, 
                  enable_anonymous: e.target.checked 
                })}
                className="w-4 h-4"
              />
              <span className="text-ink">允许匿名发布</span>
            </label>
          </div>
        </Card>

        <Button onClick={handleSave} className="w-full">
          <Save size={16} className="mr-2" />
          保存设置
        </Button>
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

export default AdminSettingsPage;

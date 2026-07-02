import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { postsApi } from '../services/posts';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Input } from '../components/ui/Input';
import { Toast } from '../components/ui/Toast';
import { MapPin } from 'lucide-react';

const PublishPage: React.FC = () => {
  const navigate = useNavigate();
  const [formData, setFormData] = useState({
    title: '',
    content: '',
    category_id: '',
    location_name: '',
    location_lat: '',
    location_lng: '',
    is_anonymous: false,
  });
  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' | 'warning' | 'info' } | null>(null);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    const { name, value, type } = e.target;
    if (type === 'checkbox') {
      setFormData(prev => ({ ...prev, [name]: (e.target as HTMLInputElement).checked }));
    } else {
      setFormData(prev => ({ ...prev, [name]: value }));
    }
  };

  // 手绘风分类按钮：更新 formData.category_id（保持状态结构不变）
  const handleCategorySelect = (id: number) => {
    setFormData(prev => ({ ...prev, category_id: String(id) }));
  };

  const handleSubmit = async (e: React.FormEvent, status: 'draft' | 'pending' = 'pending') => {
    e.preventDefault();

    if (!formData.title || !formData.content || !formData.category_id) {
      setToast({ message: '请填写所有必填项', type: 'warning' });
      return;
    }

    if (formData.title.length < 5 || formData.title.length > 100) {
      setToast({ message: '标题长度必须在5-100字符之间', type: 'warning' });
      return;
    }

    if (formData.content.length < 10 || formData.content.length > 5000) {
      setToast({ message: '内容长度必须在10-5000字符之间', type: 'warning' });
      return;
    }

    setLoading(true);
    try {
      await postsApi.createPost({
        title: formData.title,
        content: formData.content,
        category_id: Number(formData.category_id),
        location_id: 1, // 默认地点，实际应让用户选择
        is_anonymous: formData.is_anonymous,
        status, // T-B-06: draft 草稿 / pending 提交审核
      });
      setToast({
        message: status === 'draft' ? '草稿已保存' : '已提交审核，等待管理员通过',
        type: 'success',
      });
      setTimeout(() => navigate('/'), 1000);
    } catch (error: any) {
      const message = error.response?.data?.detail || '操作失败，请稍后重试';
      setToast({ message, type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const categories = [
    { id: 1, name: '校园美食', emoji: '🍜' },
    { id: 2, name: '校园动物', emoji: '🐈' },
    { id: 3, name: '打印服务', emoji: '🖨️' },
    { id: 4, name: '失物招领', emoji: '🔍' },
    { id: 5, name: '二手交易', emoji: '📦' },
    { id: 6, name: '学习交流', emoji: '📚' },
    { id: 7, name: '社团活动', emoji: '🎪' },
    { id: 8, name: '校园设施', emoji: '🏫' },
    { id: 9, name: '兼职实习', emoji: '💼' },
    { id: 10, name: '校园交通', emoji: '🚌' },
    { id: 11, name: '生活服务', emoji: '🧺' },
    { id: 12, name: '其他', emoji: '✨' },
  ];

  return (
    <div className="max-w-2xl mx-auto px-1 py-2">
      {/* 页面标题：楷体 */}
      <header className="mb-7">
        <span className="eyebrow">New Moment</span>
        <h1 className="font-display font-extrabold text-[30px] leading-tight tracking-[0.06em] text-lake mt-2">
          发布此刻
        </h1>
        <p className="text-ink-sub text-sm mt-1.5">把会消失的校园经验留下来</p>
      </header>

      {/* 表单卡片：Card variant=elevated */}
      <Card variant="elevated" padding="lg">
        <form onSubmit={(e) => handleSubmit(e, 'pending')} className="space-y-5">
          <Input
            label="标题"
            name="title"
            type="text"
            value={formData.title}
            onChange={handleChange}
            placeholder="请输入标题（5-100字符）"
            required
          />

          {/* 分类选择：手绘风按钮 */}
          <div>
            <label className="block text-sm font-medium text-ink mb-2 font-sans">
              分类 <span className="text-danger">*</span>
            </label>
            <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
              {categories.map(cat => {
                const isActive = formData.category_id === String(cat.id);
                return (
                  <button
                    key={cat.id}
                    type="button"
                    onClick={() => handleCategorySelect(cat.id)}
                    className={`flex items-center gap-1.5 px-3 py-2.5 rounded-md text-xs font-medium transition-all ${
                      isActive
                        ? 'bg-lake text-white shadow-lake'
                        : 'bg-mist text-ink-sub hover:bg-line hover:-translate-y-0.5'
                    }`}
                  >
                    <span className="text-sm">{cat.emoji}</span>
                    <span className="truncate">{cat.name}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* 内容：textarea */}
          <div>
            <label className="block text-sm font-medium text-ink mb-2 font-sans">
              内容 <span className="text-danger">*</span>
            </label>
            <textarea
              name="content"
              value={formData.content}
              onChange={handleChange}
              placeholder="请输入内容（10-5000字符）"
              rows={8}
              className="w-full px-3.5 py-3 bg-white/78 border border-line rounded-md text-sm text-ink placeholder:text-ink-muted/70 focus:outline-none focus:bg-white focus:border-lake focus:shadow-sm transition-all resize-none"
              required
            />
          </div>

          <Input
            label="地点名称"
            name="location_name"
            type="text"
            value={formData.location_name}
            onChange={handleChange}
            placeholder="例如：图书馆、食堂、教学楼等"
            icon={<MapPin size={18} />}
          />

          <div className="grid grid-cols-2 gap-4">
            <Input
              label="纬度"
              name="location_lat"
              type="number"
              value={formData.location_lat}
              onChange={handleChange}
              placeholder="例如：31.4837"
              step="0.0001"
            />
            <Input
              label="经度"
              name="location_lng"
              type="number"
              value={formData.location_lng}
              onChange={handleChange}
              placeholder="例如：120.2712"
              step="0.0001"
            />
          </div>

          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              name="is_anonymous"
              checked={formData.is_anonymous}
              onChange={handleChange}
              className="w-4 h-4 text-lake border-line rounded focus:ring-lamp/40"
            />
            <label className="text-sm text-ink">匿名发布</label>
          </div>

          {/* 提示信息：淡绿色背景卡片 */}
          <div className="bg-grass/12 text-[#476a51] rounded-md px-4 py-3 text-xs leading-relaxed border border-grass/20">
            信息会过期，也能被更新。每条信息都有"最后确认时间"，路过时点一下仍然有效，就能帮后来的人少走弯路。
            <br />
            <span className="text-[#5a8266]">提示：</span>可先"存为草稿"稍后再"提交审核"，审核通过后才会公开展示。
          </div>

          <div className="flex gap-3 pt-2">
            {/* T-B-06: 提交审核（默认） */}
            <Button
              type="submit"
              variant="primary"
              size="lg"
              loading={loading}
              className="flex-1"
            >
              提交审核
            </Button>
            {/* T-B-06: 存为草稿 */}
            <Button
              type="button"
              variant="secondary"
              size="lg"
              loading={loading}
              onClick={(e) => handleSubmit(e as unknown as React.FormEvent, 'draft')}
            >
              存为草稿
            </Button>
            <Button
              type="button"
              variant="text"
              size="lg"
              onClick={() => navigate(-1)}
            >
              取消
            </Button>
          </div>
        </form>
      </Card>

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

export default PublishPage;

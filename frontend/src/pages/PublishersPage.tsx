import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { Input } from '../components/ui/Input';
import { Modal } from '../components/ui/Modal';
import { Loading } from '../components/ui/Loading';
import { publishersApi } from '../services/publishers';
import { useUIStore } from '../store/useUIStore';
import { useAuthStore } from '../store/useAuthStore';
import type {
  PublisherBrief,
  PublisherDetail,
  PublisherAggregation,
  PublisherType,
  PublisherVerifiedStatus,
  PublisherCreateRequest,
} from '../types';
import {
  Building2,
  Search,
  Plus,
  CheckCircle2,
  Eye,
  Share2,
  ThumbsUp,
  ThumbsDown,
  HelpCircle,
  RefreshCw,
  ArrowLeft,
  MapPin,
  Clock,
  Phone,
  Users,
} from 'lucide-react';

const PAGE_SIZE = 12;

const TYPE_LABELS: Record<PublisherType, string> = {
  department: '部门',
  club: '社团',
  service_org: '服务组织',
};

const STATUS_LABELS: Record<PublisherVerifiedStatus, { label: string; variant: 'success' | 'warning' | 'danger' | 'default' }> = {
  pending: { label: '待认证', variant: 'warning' },
  verified: { label: '已认证', variant: 'success' },
  revoked: { label: '已撤销', variant: 'danger' },
  rejected: { label: '已驳回', variant: 'default' },
};

/** ORG-01.1: 发布主体主页（列表 + 详情 + 申请创建） */
const PublishersPage: React.FC = () => {
  const navigate = useNavigate();
  const { publisherId } = useParams<{ publisherId?: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const showToast = useUIStore((s) => s.showToast);
  const { isAuthenticated } = useAuthStore();

  // 解析 URL 参数
  const focusId = publisherId ? Number(publisherId) : null;

  if (focusId !== null) {
    return <PublisherDetailView publisherId={focusId} onBack={() => navigate('/publishers')} />;
  }

  return (
    <PublisherListView
      keyword={searchParams.get('keyword') || ''}
      typeFilter={(searchParams.get('type') as PublisherType | null) || null}
      onKeywordChange={(v) => {
        const next = new URLSearchParams(searchParams);
        if (v) next.set('keyword', v);
        else next.delete('keyword');
        setSearchParams(next);
      }}
      onTypeChange={(v) => {
        const next = new URLSearchParams(searchParams);
        if (v) next.set('type', v);
        else next.delete('type');
        setSearchParams(next);
      }}
      onOpenDetail={(id) => navigate(`/publishers/${id}`)}
      showToast={showToast}
      isAuthenticated={isAuthenticated}
    />
  );
};

// ============================================================
// 列表视图
// ============================================================
interface ListViewProps {
  keyword: string;
  typeFilter: PublisherType | null;
  onKeywordChange: (v: string) => void;
  onTypeChange: (v: PublisherType | null) => void;
  onOpenDetail: (id: number) => void;
  showToast: (msg: string, type?: 'success' | 'error' | 'warning' | 'info') => void;
  isAuthenticated: boolean;
}

const PublisherListView: React.FC<ListViewProps> = ({
  keyword,
  typeFilter,
  onKeywordChange,
  onTypeChange,
  onOpenDetail,
  showToast,
  isAuthenticated,
}) => {
  const [items, setItems] = useState<PublisherBrief[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [searchInput, setSearchInput] = useState(keyword);
  const [createOpen, setCreateOpen] = useState(false);

  const loadList = useCallback(async (p: number) => {
    try {
      setLoading(true);
      const data = await publishersApi.list({
        page: p,
        page_size: PAGE_SIZE,
        keyword: keyword || undefined,
        type: typeFilter || undefined,
      });
      setItems(data.items);
      setTotal(data.total);
      setTotalPages(data.total_pages);
    } catch (err) {
      const msg = err instanceof Error ? err.message : '加载失败';
      showToast(msg, 'error');
    } finally {
      setLoading(false);
    }
  }, [keyword, typeFilter, showToast]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setPage(1);
    void loadList(1);
  }, [loadList]);

  useEffect(() => {
    void loadList(page);
  }, [page, loadList]);

  const handleSearch = () => {
    onKeywordChange(searchInput);
  };

  return (
    <div className="max-w-5xl mx-auto py-4 px-4">
      {/* 页头 */}
      <header className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="font-display font-bold text-[24px] tracking-wide text-lake leading-tight flex items-center gap-2">
            <Building2 size={24} />
            官方发布主体
          </h1>
          <p className="text-ink-muted text-sm mt-1">
            部门、社团、服务组织认证主页 · 共 {total} 个主体
          </p>
        </div>
        {isAuthenticated && (
          <Button size="sm" variant="primary" onClick={() => setCreateOpen(true)}>
            <Plus size={14} className="mr-1" />
            申请主体
          </Button>
        )}
      </header>

      {/* 筛选栏 */}
      <Card variant="outlined" padding="sm" className="mb-4">
        <div className="flex flex-wrap items-center gap-2">
          {[
            { value: null, label: '全部' },
            { value: 'department', label: '部门' },
            { value: 'club', label: '社团' },
            { value: 'service_org', label: '服务组织' },
          ].map((opt) => (
            <button
              key={opt.value || 'all'}
              onClick={() => onTypeChange(opt.value as PublisherType | null)}
              className={`px-3 py-1.5 rounded-md text-xs transition-colors ${
                typeFilter === opt.value
                  ? 'bg-lake text-paper'
                  : 'bg-mist text-ink-sub hover:text-ink'
              }`}
            >
              {opt.label}
            </button>
          ))}
          <div className="flex items-center gap-2 ml-auto">
            <Input
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              placeholder="搜索主体名称"
              className="w-44"
            />
            <Button size="sm" variant="secondary" onClick={handleSearch}>
              <Search size={13} className="mr-1" />
              搜索
            </Button>
          </div>
        </div>
      </Card>

      {/* 主体列表 */}
      {loading && items.length === 0 ? (
        <div className="py-20">
          <Loading />
        </div>
      ) : items.length === 0 ? (
        <Card padding="lg" className="text-center py-16">
          <Building2 size={48} className="mx-auto text-ink-disabled mb-4" />
          <p className="text-ink-sub">暂无发布主体</p>
        </Card>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {items.map((p) => {
            const statusInfo = STATUS_LABELS[p.verified_status];
            return (
              <Card
                key={p.id}
                variant="outlined"
                padding="md"
                onClick={() => onOpenDetail(p.id)}
              >
                <div className="flex items-start gap-3">
                  <div className="w-12 h-12 rounded-xl bg-mist flex items-center justify-center flex-shrink-0 overflow-hidden">
                    {p.logo_url ? (
                      <img src={p.logo_url} alt={p.name} className="w-full h-full object-cover" />
                    ) : (
                      <Building2 size={22} className="text-ink-sub" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5 mb-1">
                      <h3 className="font-semibold text-ink line-clamp-1">{p.name}</h3>
                      {p.verified_status === 'verified' && (
                        <CheckCircle2 size={14} className="text-grass flex-shrink-0" />
                      )}
                    </div>
                    <div className="flex items-center gap-1.5 mb-2">
                      <Badge variant="default">{TYPE_LABELS[p.type]}</Badge>
                      <Badge variant={statusInfo.variant}>{statusInfo.label}</Badge>
                    </div>
                    {p.intro && (
                      <p className="text-xs text-ink-sub line-clamp-2">{p.intro}</p>
                    )}
                    <div className="flex items-center gap-3 mt-2 text-xs text-ink-muted">
                      <span className="flex items-center gap-0.5">
                        <Eye size={11} /> {p.view_count}
                      </span>
                      <span className="flex items-center gap-0.5">
                        <Users size={11} /> {p.subscribe_count}
                      </span>
                    </div>
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}

      {/* 分页 */}
      {totalPages > 1 && (
        <div className="flex justify-center items-center gap-2 mt-6">
          <Button
            size="sm"
            variant="text"
            disabled={page === 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            上一页
          </Button>
          <span className="text-sm text-ink-sub">
            {page} / {totalPages}
          </span>
          <Button
            size="sm"
            variant="text"
            disabled={page === totalPages}
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
          >
            下一页
          </Button>
        </div>
      )}

      {/* 申请创建主体弹窗 */}
      {createOpen && (
        <CreatePublisherModal
          onClose={() => setCreateOpen(false)}
          onSuccess={(id) => {
            setCreateOpen(false);
            showToast('申请已提交，等待管理员认证', 'success');
            onOpenDetail(id);
          }}
          showToast={showToast}
        />
      )}
    </div>
  );
};

// ============================================================
// 详情视图
// ============================================================
interface DetailViewProps {
  publisherId: number;
  onBack: () => void;
}

const PublisherDetailView: React.FC<DetailViewProps> = ({ publisherId, onBack }) => {
  const showToast = useUIStore((s) => s.showToast);
  const [detail, setDetail] = useState<PublisherDetail | null>(null);
  const [aggregation, setAggregation] = useState<PublisherAggregation | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const [d, agg] = await Promise.all([
        publishersApi.getDetail(publisherId),
        publishersApi.getAggregation(publisherId),
      ]);
      setDetail(d);
      setAggregation(agg);
    } catch (err) {
      const msg = err instanceof Error ? err.message : '加载失败';
      showToast(msg, 'error');
    } finally {
      setLoading(false);
    }
  }, [publisherId, showToast]);

  useEffect(() => {
    void load();
  }, [load]);

  const handleFeedback = async (type: 'valid' | 'invalid' | 'zero_result') => {
    try {
      await publishersApi.submitFeedback(publisherId, type);
      const labels: Record<typeof type, string> = {
        valid: '已记录"内容有效"',
        invalid: '已记录"内容无效"',
        zero_result: '已记录"未找到所需"',
      };
      showToast(labels[type], 'success');
      void load();
    } catch (err) {
      const msg = err instanceof Error ? err.message : '提交失败';
      showToast(msg, 'error');
    }
  };

  const handleShare = async () => {
    try {
      await publishersApi.share(publisherId);
      showToast('分享已记录', 'success');
      void load();
    } catch {
      // 静默处理
    }
  };

  if (loading && !detail) {
    return (
      <div className="max-w-4xl mx-auto py-8 px-4">
        <Loading />
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="max-w-4xl mx-auto py-8 px-4">
        <Card padding="lg" className="text-center py-16">
          <Building2 size={48} className="mx-auto text-ink-disabled mb-4" />
          <p className="text-ink-sub mb-4">发布主体不存在或已被删除</p>
          <Button variant="secondary" onClick={onBack}>
            返回列表
          </Button>
        </Card>
      </div>
    );
  }

  const statusInfo = STATUS_LABELS[detail.verified_status];

  return (
    <div className="max-w-4xl mx-auto py-4 px-4">
      {/* 返回 */}
      <button
        onClick={onBack}
        className="flex items-center gap-1 text-sm text-ink-sub hover:text-ink mb-4 transition-colors"
      >
        <ArrowLeft size={14} />
        返回主体列表
      </button>

      {/* 主体头部 */}
      <Card variant="elevated" padding="lg" className="mb-4">
        <div className="flex items-start gap-4">
          <div className="w-16 h-16 rounded-2xl bg-mist flex items-center justify-center flex-shrink-0 overflow-hidden">
            {detail.logo_url ? (
              <img src={detail.logo_url} alt={detail.name} className="w-full h-full object-cover" />
            ) : (
              <Building2 size={28} className="text-ink-sub" />
            )}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-2 flex-wrap">
              <h1 className="font-display font-bold text-[22px] text-ink">{detail.name}</h1>
              <Badge variant="default">{TYPE_LABELS[detail.type]}</Badge>
              <Badge variant={statusInfo.variant}>
                {statusInfo.label}
              </Badge>
              {detail.is_member && detail.my_role && (
                <Badge variant="info">我是{detail.my_role === 'owner' ? '负责人' : detail.my_role === 'admin' ? '管理员' : '成员'}</Badge>
              )}
            </div>
            {detail.intro && (
              <p className="text-sm text-ink-sub mb-3">{detail.intro}</p>
            )}
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-ink-muted">
              {detail.location_name && (
                <span className="flex items-center gap-1">
                  <MapPin size={12} /> {detail.location_name}
                </span>
              )}
              {detail.service_hours && (
                <span className="flex items-center gap-1">
                  <Clock size={12} /> {detail.service_hours}
                </span>
              )}
              {detail.contact && (
                <span className="flex items-center gap-1">
                  <Phone size={12} /> {detail.contact}
                </span>
              )}
            </div>
          </div>
        </div>

        {/* 反馈按钮组 */}
        <div className="flex flex-wrap items-center gap-2 mt-4 pt-4 border-t border-ink-divider">
          <Button size="sm" variant="secondary" onClick={() => handleFeedback('valid')}>
            <ThumbsUp size={13} className="mr-1" />
            内容有效
          </Button>
          <Button size="sm" variant="secondary" onClick={() => handleFeedback('invalid')}>
            <ThumbsDown size={13} className="mr-1" />
            内容无效
          </Button>
          <Button size="sm" variant="secondary" onClick={() => handleFeedback('zero_result')}>
            <HelpCircle size={13} className="mr-1" />
            未找到所需
          </Button>
          <Button size="sm" variant="text" onClick={handleShare} className="ml-auto">
            <Share2 size={13} className="mr-1" />
            分享
          </Button>
        </div>
      </Card>

      {/* 聚合效果（ORG-01.4） */}
      {aggregation && (
        <Card variant="outlined" padding="md" className="mb-4">
          <h2 className="text-sm font-semibold text-ink mb-3 flex items-center gap-1.5">
            <RefreshCw size={14} />
            聚合效果
          </h2>
          <div className="grid grid-cols-3 sm:grid-cols-5 gap-3">
            <AggItem label="浏览" value={aggregation.view_count} />
            <AggItem label="订阅" value={aggregation.subscribe_count} />
            <AggItem label="分享" value={aggregation.share_count} />
            <AggItem label="有效反馈" value={aggregation.valid_feedback_count} />
            <AggItem label="未找到" value={aggregation.zero_result_count} />
          </div>
          <div className="grid grid-cols-3 gap-3 mt-3 pt-3 border-t border-ink-divider">
            <AggItem label="内容总数" value={aggregation.total_posts} />
            <AggItem label="已发布" value={aggregation.published_posts} />
            <AggItem label="待审核" value={aggregation.pending_posts} />
          </div>
          {aggregation.valid_rate !== null && aggregation.valid_rate !== undefined && (
            <p className="text-xs text-ink-sub mt-3">
              有效性反馈率：{(aggregation.valid_rate * 100).toFixed(1)}%
            </p>
          )}
        </Card>
      )}

      {/* 最近内容 */}
      {detail.recent_posts.length > 0 && (
        <Card variant="outlined" padding="md" className="mb-4">
          <h2 className="text-sm font-semibold text-ink mb-3">最近内容</h2>
          <div className="space-y-2">
            {detail.recent_posts.map((post) => (
              <div
                key={post.id}
                className="flex items-center justify-between p-3 rounded-lg bg-mist/40 hover:bg-mist transition-colors cursor-pointer"
                onClick={() => {
                  window.location.href = `/posts/${post.id}`;
                }}
              >
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-ink line-clamp-1">{post.title}</p>
                  <div className="flex items-center gap-2 mt-0.5 text-xs text-ink-muted">
                    {post.category_name && <span>{post.category_name}</span>}
                    <span className="flex items-center gap-0.5">
                      <Eye size={10} /> {post.view_count}
                    </span>
                  </div>
                </div>
                <span className="text-xs text-ink-muted flex-shrink-0 ml-2">
                  {new Date(post.created_at).toLocaleDateString('zh-CN')}
                </span>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* 成员列表 */}
      {detail.memberships.length > 0 && (
        <Card variant="outlined" padding="md">
          <h2 className="text-sm font-semibold text-ink mb-3">主体成员（{detail.memberships.length}）</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {detail.memberships.map((m) => (
              <div key={m.id} className="flex items-center gap-2 p-2 rounded-lg bg-mist/40">
                <div className="w-8 h-8 rounded-full bg-paper-hover flex items-center justify-center text-xs font-medium text-ink-sub">
                  {m.user_nickname?.charAt(0) || '?'}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-ink line-clamp-1">{m.user_nickname || `用户${m.user_id}`}</p>
                  <p className="text-xs text-ink-muted">{m.user_email}</p>
                </div>
                <Badge variant={m.role === 'owner' ? 'info' : 'default'}>
                  {m.role === 'owner' ? '负责人' : m.role === 'admin' ? '管理员' : '成员'}
                </Badge>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
};

const AggItem: React.FC<{ label: string; value: number }> = ({ label, value }) => (
  <div className="text-center">
    <p className="text-lg font-bold text-lake">{value}</p>
    <p className="text-xs text-ink-sub mt-0.5">{label}</p>
  </div>
);

// ============================================================
// 创建主体弹窗
// ============================================================
interface CreateModalProps {
  onClose: () => void;
  onSuccess: (id: number) => void;
  showToast: (msg: string, type?: 'success' | 'error' | 'warning' | 'info') => void;
}

const CreatePublisherModal: React.FC<CreateModalProps> = ({ onClose, onSuccess, showToast }) => {
  const [form, setForm] = useState<PublisherCreateRequest>({
    name: '',
    type: 'department',
    intro: '',
    logo_url: '',
    service_hours: '',
    contact: '',
  });
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async () => {
    if (!form.name.trim()) {
      showToast('请输入主体名称', 'warning');
      return;
    }
    try {
      setSubmitting(true);
      // 关键：verified_status 由后端强制为 pending，前端不传
      const detail = await publishersApi.create({
        ...form,
        intro: form.intro?.trim() || undefined,
        logo_url: form.logo_url?.trim() || undefined,
        service_hours: form.service_hours?.trim() || undefined,
        contact: form.contact?.trim() || undefined,
      });
      onSuccess(detail.id);
    } catch (err) {
      const msg = err instanceof Error ? err.message : '申请失败';
      showToast(msg, 'error');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal isOpen onClose={onClose} title="申请创建发布主体" size="lg">
      <div className="px-6 py-5 space-y-4">
        <div className="bg-sun/10 border border-sun/30 rounded-lg p-3 text-xs text-[#b89230]">
          <p className="font-medium mb-1">认证说明</p>
          <p>提交后状态为「待认证」，需校级管理员审核通过后才能获得认证标识。认证不代表内容免审——发布内容仍走原审核流程。</p>
        </div>

        <div>
          <label className="block text-sm font-medium text-ink mb-1">
            主体名称 <span className="text-danger">*</span>
          </label>
          <Input
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder="如：校学生会、图书馆、食堂管理处"
            maxLength={100}
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-ink mb-1">
            主体类型 <span className="text-danger">*</span>
          </label>
          <div className="flex gap-2">
            {([
              { value: 'department', label: '部门' },
              { value: 'club', label: '社团' },
              { value: 'service_org', label: '服务组织' },
            ] as const).map((opt) => (
              <button
                key={opt.value}
                onClick={() => setForm({ ...form, type: opt.value })}
                className={`px-3 py-1.5 rounded-md text-sm transition-colors ${
                  form.type === opt.value
                    ? 'bg-lake text-paper'
                    : 'bg-mist text-ink-sub hover:text-ink'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-ink mb-1">简介</label>
          <textarea
            value={form.intro}
            onChange={(e) => setForm({ ...form, intro: e.target.value })}
            placeholder="主体职能、服务范围等"
            maxLength={2000}
            rows={3}
            className="w-full px-3 py-2 rounded-[10px] border border-line bg-paper text-ink text-sm placeholder:text-ink-disabled focus:outline-none focus:border-lake transition-colors"
          />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-sm font-medium text-ink mb-1">服务时间</label>
            <Input
              value={form.service_hours}
              onChange={(e) => setForm({ ...form, service_hours: e.target.value })}
              placeholder="如：周一至周五 9:00-17:00"
              maxLength={200}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-ink mb-1">联系方式</label>
            <Input
              value={form.contact}
              onChange={(e) => setForm({ ...form, contact: e.target.value })}
              placeholder="电话/邮箱/公众号"
              maxLength={255}
            />
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-ink mb-1">Logo URL</label>
          <Input
            value={form.logo_url}
            onChange={(e) => setForm({ ...form, logo_url: e.target.value })}
            placeholder="https://..."
            maxLength={500}
          />
        </div>
      </div>

      <div className="flex justify-end gap-2 px-6 py-4 border-t border-ink-divider bg-mist/30">
        <Button variant="text" onClick={onClose} disabled={submitting}>
          取消
        </Button>
        <Button variant="primary" onClick={handleSubmit} loading={submitting}>
          提交申请
        </Button>
      </div>
    </Modal>
  );
};

export default PublishersPage;

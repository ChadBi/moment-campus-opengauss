import React, { useEffect, useState, useCallback } from 'react';
import { Card } from '../../components/ui/Card';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { platformApi } from '../../services/platform';
import { useUIStore } from '../../store/useUIStore';
import { useAuthStore } from '../../store/useAuthStore';
import type {
  ActivationFunnelResponse,
  ActivationFunnelItem,
  ProvisioningChecklist,
} from '../../types';
import {
  RefreshCw,
  Filter,
  Search,
  CheckCircle,
  XCircle,
  TrendingUp,
  Award,
  School as SchoolIcon,
} from 'lucide-react';

/** 开通清单阶段定义 */
const STAGES: Array<{
  key: keyof ProvisioningChecklist;
  label: string;
  color: string;
}> = [
  { key: 'brand_set', label: '品牌设置', color: 'bg-lake' },
  { key: 'admin_accepted', label: '管理员接受', color: 'bg-info' },
  { key: 'locations_imported', label: '地点导入', color: 'bg-grass' },
  { key: 'first_content', label: '首批内容', color: 'bg-lamp' },
  { key: 'first_members', label: '首批成员', color: 'bg-sun' },
];

const ActivationFunnelPage: React.FC = () => {
  const { user } = useAuthStore();
  const isSuperAdmin = user?.role === 'super_admin';
  const showToast = useUIStore((s) => s.showToast);

  const [data, setData] = useState<ActivationFunnelResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [keyword, setKeyword] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [activeFilter, setActiveFilter] = useState<string>('');

  const loadData = useCallback(async () => {
    try {
      const resp = await platformApi.getActivationFunnel({
        keyword: keyword || undefined,
        is_active:
          activeFilter === '' ? undefined : activeFilter === 'true',
      });
      setData(resp);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : '加载激活漏斗失败';
      showToast(message, 'error');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [keyword, activeFilter, showToast]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadData();
  }, [loadData]);

  const handleRefresh = () => {
    setRefreshing(true);
    void loadData();
  };

  const handleSearch = () => {
    setKeyword(searchInput);
  };

  if (!isSuperAdmin) {
    return (
      <div className="py-16 text-center">
        <p className="text-ink-sub">仅超级管理员可访问激活漏斗</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="py-16 flex items-center justify-center">
        <div className="flex items-center gap-3 text-ink-muted">
          <div className="w-5 h-5 border-2 border-lake/30 border-t-lake rounded-full animate-spin" />
          <span>加载中...</span>
        </div>
      </div>
    );
  }

  // 各阶段完成统计
  const stageCounts = STAGES.map((stage) => ({
    ...stage,
    count: data
      ? data.items.filter((item) => item.checklist[stage.key]).length
      : 0,
  }));

  return (
    <div className="space-y-6">
      {/* 页面标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-ink">激活漏斗</h1>
          <p className="text-ink-sub text-sm mt-1">
            各校开通清单完成阶段与激活状态
          </p>
        </div>
        <Button
          variant="secondary"
          size="sm"
          icon={<RefreshCw size={14} />}
          loading={refreshing}
          onClick={handleRefresh}
        >
          刷新
        </Button>
      </div>

      {/* 汇总指标 */}
      {data && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Card variant="outlined" padding="md">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-md bg-lake/10">
                <SchoolIcon className="text-lake" size={20} />
              </div>
              <div>
                <p className="text-xs text-ink-muted">学校总数</p>
                <p className="text-xl font-bold text-ink">{data.total}</p>
              </div>
            </div>
          </Card>
          <Card variant="outlined" padding="md">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-md bg-grass/10">
                <Award className="text-grass" size={20} />
              </div>
              <div>
                <p className="text-xs text-ink-muted">已激活</p>
                <p className="text-xl font-bold text-ink">
                  {data.activated_count}
                </p>
              </div>
            </div>
          </Card>
          <Card variant="outlined" padding="md">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-md bg-lamp/10">
                <TrendingUp className="text-lamp" size={20} />
              </div>
              <div>
                <p className="text-xs text-ink-muted">激活率</p>
                <p className="text-xl font-bold text-ink">
                  {data.total > 0
                    ? `${Math.round(
                        (data.activated_count / data.total) * 100
                      )}%`
                    : '0%'}
                </p>
              </div>
            </div>
          </Card>
          <Card variant="outlined" padding="md">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-md bg-info/10">
                <CheckCircle className="text-info" size={20} />
              </div>
              <div>
                <p className="text-xs text-ink-muted">平均阶段</p>
                <p className="text-xl font-bold text-ink">
                  {data.avg_activated_stage.toFixed(1)} / 5
                </p>
              </div>
            </div>
          </Card>
        </div>
      )}

      {/* 阶段漏斗图 */}
      {data && data.total > 0 && (
        <Card variant="outlined" padding="md">
          <h2 className="text-base font-semibold text-ink mb-4">
            各阶段完成学校数
          </h2>
          <div className="space-y-3">
            {stageCounts.map((stage) => {
              const pct =
                data.total > 0
                  ? Math.round((stage.count / data.total) * 100)
                  : 0;
              return (
                <div key={stage.key} className="flex items-center gap-3">
                  <span className="text-sm text-ink-sub w-24 shrink-0">
                    {stage.label}
                  </span>
                  <div className="flex-1 h-7 bg-paper-hover rounded-md overflow-hidden relative">
                    <div
                      className={`${stage.color} h-full rounded-md transition-all duration-500 flex items-center justify-end px-2`}
                      style={{ width: `${Math.max(pct, 8)}%` }}
                    >
                      <span className="text-xs text-paper font-medium">
                        {stage.count}
                      </span>
                    </div>
                  </div>
                  <span className="text-xs text-ink-muted w-10 text-right">
                    {pct}%
                  </span>
                </div>
              );
            })}
          </div>
        </Card>
      )}

      {/* 筛选栏 */}
      <div className="flex items-center gap-2 flex-wrap">
        <div className="flex items-center gap-2 flex-1 min-w-[200px]">
          <input
            type="text"
            placeholder="按名称或 code 搜索"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') handleSearch();
            }}
            className="flex-1 h-9 px-3.5 bg-paper border border-line rounded-[10px] text-sm text-ink focus:outline-none focus:border-lake"
          />
          <Button
            variant="primary"
            size="sm"
            icon={<Search size={14} />}
            onClick={handleSearch}
          >
            搜索
          </Button>
        </div>
        <div className="flex items-center gap-1">
          <Filter size={14} className="text-ink-muted" />
          <select
            value={activeFilter}
            onChange={(e) => setActiveFilter(e.target.value)}
            className="select-nice-sm w-auto"
          >
            <option value="">全部</option>
            <option value="true">已激活</option>
            <option value="false">未激活</option>
          </select>
        </div>
      </div>

      {/* 学校列表 */}
      {data && data.items.length > 0 ? (
        <div className="space-y-2">
          {data.items.map((item: ActivationFunnelItem) => (
            <Card key={item.school_id} variant="outlined" padding="md">
              <div className="flex items-start justify-between gap-3 flex-wrap">
                {/* 学校信息 */}
                <div className="flex items-center gap-2 min-w-[180px]">
                  <div className="w-9 h-9 rounded-md bg-lake/10 grid place-items-center text-lake">
                    <SchoolIcon size={18} />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-ink">
                        {item.school_name}
                      </span>
                      <Badge variant="info">{item.school_code}</Badge>
                    </div>
                    <div className="flex items-center gap-1.5 mt-0.5">
                      <Badge
                        variant={item.is_active ? 'success' : 'danger'}
                      >
                        {item.is_active ? '启用' : '暂停'}
                      </Badge>
                      {item.plan_code && (
                        <Badge variant="default">{item.plan_code}</Badge>
                      )}
                      {item.activated && (
                        <Badge variant="success">
                          <CheckCircle size={10} className="mr-0.5" />
                          已激活
                        </Badge>
                      )}
                    </div>
                  </div>
                </div>

                {/* 阶段进度 */}
                <div className="flex-1 min-w-[280px]">
                  <div className="flex items-center gap-1.5 mb-1.5">
                    <span className="text-xs text-ink-muted">
                      阶段进度
                    </span>
                    <span className="text-xs font-medium text-ink">
                      {item.activated_stage} / 5
                    </span>
                    <div className="flex-1 h-1.5 bg-paper-hover rounded-full overflow-hidden">
                      <div
                        className="h-full bg-grass rounded-full transition-all duration-500"
                        style={{
                          width: `${(item.activated_stage / 5) * 100}%`,
                        }}
                      />
                    </div>
                  </div>
                  <div className="flex items-center gap-1 flex-wrap">
                    {STAGES.map((stage) => {
                      const done = item.checklist[stage.key];
                      return (
                        <div
                          key={stage.key}
                          className={`flex items-center gap-0.5 px-1.5 py-0.5 rounded text-xs ${
                            done
                              ? 'bg-grass/10 text-grass'
                              : 'bg-paper-hover text-ink-muted'
                          }`}
                        >
                          {done ? (
                            <CheckCircle size={11} />
                          ) : (
                            <XCircle size={11} />
                          )}
                          <span>{stage.label}</span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            </Card>
          ))}
        </div>
      ) : (
        <Card variant="filled" padding="md">
          <p className="text-center text-ink-muted text-sm">
            {data ? '暂无学校数据' : '加载失败'}
          </p>
        </Card>
      )}
    </div>
  );
};

export default ActivationFunnelPage;

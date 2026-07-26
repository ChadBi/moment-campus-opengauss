import React, { useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Badge } from '../../components/ui/Badge';
import { Input } from '../../components/ui/Input';
import { Table, Pagination, type Column } from '../../components/ui/Table';
import { adminApi, type LocationAdmin } from '../../services/admin';
import { useUIStore } from '../../store/useUIStore';
import { MapPin, Check, X, Search } from 'lucide-react';
import { logger } from '../../utils/logger';
import { formatShortDateTime as formatDate } from '../../utils/date';

const PAGE_SIZE = 10;

/** ADM-01.6: 地点核验队列（待办卡片入口 /admin/locations?verified=false） */
const AdminLocationsPage: React.FC = () => {
  const showToast = useUIStore((s) => s.showToast);
  const [searchParams, setSearchParams] = useSearchParams();

  // URL 筛选：verified=true/false（待办卡片跳转带 verified=false）
  const verifiedParam = searchParams.get('verified') || '';
  const isVerifiedFilter: boolean | undefined =
    verifiedParam === 'true' ? true : verifiedParam === 'false' ? false : undefined;

  const [locations, setLocations] = useState<LocationAdmin[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [keyword, setKeyword] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [actingId, setActingId] = useState<number | null>(null);

  const loadLocations = useCallback(async (p: number) => {
    try {
      const data = await adminApi.getAdminLocations({
        page: p,
        page_size: PAGE_SIZE,
        is_verified: isVerifiedFilter,
        keyword: keyword || undefined,
      });
      setLocations(data.items);
      setTotal(data.total);
      setTotalPages(data.total_pages);
    } catch (error) {
      logger.error('加载地点列表失败:', error);
      showToast('加载地点列表失败', 'error');
    } finally {
      setLoading(false);
    }
  }, [isVerifiedFilter, keyword, showToast]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadLocations(page);
  }, [page, loadLocations]);

  const updateVerifiedFilter = (value: string) => {
    const next = new URLSearchParams(searchParams);
    if (value) {
      next.set('verified', value);
    } else {
      next.delete('verified');
    }
    setSearchParams(next);
    setPage(1);
    setLoading(true);
  };

  const handleSearch = () => {
    setKeyword(searchInput);
    setPage(1);
    setLoading(true);
  };

  const handleVerify = async (loc: LocationAdmin, target: boolean) => {
    setActingId(loc.id);
    try {
      await adminApi.verifyLocation(loc.id, target);
      showToast(target ? `已核验「${loc.name}」` : `已取消「${loc.name}」核验`, 'success');
      void loadLocations(page);
    } catch (error) {
      const message = error instanceof Error ? error.message : '操作失败';
      showToast(message, 'error');
    } finally {
      setActingId(null);
    }
  };

  const columns: Column<LocationAdmin>[] = [
    {
      key: 'name',
      title: '地点名称',
      render: (value, row) => (
        <div className="min-w-0">
          <p className="font-medium text-ink line-clamp-1">{value}</p>
          <p className="text-xs text-ink-muted line-clamp-1 mt-0.5">
            {[row.building, row.floor].filter(Boolean).join(' · ') || row.description || '—'}
          </p>
        </div>
      ),
    },
    {
      key: 'latitude',
      title: '坐标',
      width: 170,
      nowrap: true,
      render: (_, row) => (
        <span className="text-xs text-ink-sub">
          {row.latitude.toFixed(6)}, {row.longitude.toFixed(6)}
        </span>
      ),
    },
    {
      key: 'post_count',
      title: '关联内容',
      width: 90,
      nowrap: true,
      render: (value) => `${value} 条`,
    },
    {
      key: 'is_verified',
      title: '核验状态',
      width: 100,
      render: (value) =>
        value ? (
          <Badge variant="success">已核验</Badge>
        ) : (
          <Badge variant="warning">待核验</Badge>
        ),
    },
    {
      key: 'created_at',
      title: '创建时间',
      width: 130,
      nowrap: true,
      render: (value) => formatDate(value),
    },
    {
      key: 'actions',
      title: '操作',
      width: 120,
      nowrap: true,
      render: (_, row) =>
        row.is_verified ? (
          <Button
            size="sm"
            variant="text"
            loading={actingId === row.id}
            onClick={() => handleVerify(row, false)}
          >
            <X size={13} className="mr-1" />
            取消核验
          </Button>
        ) : (
          <Button
            size="sm"
            variant="primary"
            loading={actingId === row.id}
            onClick={() => handleVerify(row, true)}
          >
            <Check size={13} className="mr-1" />
            核验通过
          </Button>
        ),
    },
  ];

  return (
    <div className="space-y-4">
      {/* 页面标题 */}
      <div>
        <h1 className="text-2xl font-bold text-ink">地点核验</h1>
        <p className="text-ink-sub text-sm mt-1">
          用户提交的新地点需核验后才在地图/搜索中正式启用，共 {total} 个地点
        </p>
      </div>

      {/* 筛选栏 */}
      <Card variant="outlined" padding="sm">
        <div className="flex flex-wrap items-center gap-2">
          {[
            { value: '', label: '全部' },
            { value: 'false', label: '待核验' },
            { value: 'true', label: '已核验' },
          ].map((opt) => (
            <button
              key={opt.value}
              onClick={() => updateVerifiedFilter(opt.value)}
              className={`px-3 py-1.5 rounded-md text-xs transition-colors ${
                verifiedParam === opt.value
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
              placeholder="按名称搜索"
              className="w-44"
            />
            <Button size="sm" variant="secondary" onClick={handleSearch}>
              <Search size={13} className="mr-1" />
              搜索
            </Button>
          </div>
        </div>
      </Card>

      {/* 表格 */}
      {locations.length === 0 && !loading ? (
        <Card padding="lg" className="text-center py-16">
          <MapPin size={48} className="mx-auto text-ink-disabled mb-4" />
          <p className="text-ink-sub">暂无地点记录</p>
        </Card>
      ) : (
        <Table<LocationAdmin>
          columns={columns}
          data={locations}
          loading={loading}
          emptyText="暂无地点记录"
        />
      )}

      {/* 分页 */}
      <Pagination
        page={page}
        pageSize={PAGE_SIZE}
        total={total}
        totalPages={totalPages}
        onChange={(p) => setPage(p)}
      />
    </div>
  );
};

export default AdminLocationsPage;

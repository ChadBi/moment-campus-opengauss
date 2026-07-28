import React, { useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Card } from '../../components/ui/Card';
import { Button } from '../../components/ui/Button';
import { Badge } from '../../components/ui/Badge';
import { Input } from '../../components/ui/Input';
import { Table, Pagination, type Column } from '../../components/ui/Table';
import { adminApi, type LocationAdmin } from '../../services/admin';
import { useUIStore } from '../../store/useUIStore';
import { MapPin, Check, X, Search, Eye, Building2, Layers, Info } from 'lucide-react';
import MapLocationPicker from '../../components/MapLocationPicker';
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
  // Task 3.6: 详情弹窗（展示地点坐标 + 地图）
  const [detailLocation, setDetailLocation] = useState<LocationAdmin | null>(null);

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
      width: 170,
      nowrap: true,
      render: (_, row) => (
        <div className="flex items-center gap-1">
          <Button
            size="sm"
            variant="text"
            onClick={() => setDetailLocation(row)}
          >
            <Eye size={13} className="mr-1" />
            详情
          </Button>
          {row.is_verified ? (
            <Button
              size="sm"
              variant="text"
              loading={actingId === row.id}
              onClick={() => handleVerify(row, false)}
            >
              <X size={13} className="mr-1" />
              取消
            </Button>
          ) : (
            <Button
              size="sm"
              variant="primary"
              loading={actingId === row.id}
              onClick={() => handleVerify(row, true)}
            >
              <Check size={13} className="mr-1" />
              核验
            </Button>
          )}
        </div>
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

      {/* Task 6.2: 地点核验流程引导 */}
      <div className="flex items-start gap-2 bg-lake/5 border border-lake/20 rounded-lg px-4 py-3 text-sm text-ink-sub">
        <Info size={16} className="text-lake flex-shrink-0 mt-0.5" />
        <div>
          <span className="font-medium text-ink">核验流程：</span>
          用户发帖时新增地点 → <code className="text-xs bg-mist px-1.5 py-0.5 rounded">is_verified=false</code> → 管理员在此核验 → 标记 <code className="text-xs bg-mist px-1.5 py-0.5 rounded">is_verified=true</code> 后合并到正式地点列表。点击「详情」可在地图上查看地点位置。
        </div>
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

      {/* Task 3.6: 地点详情弹窗（含地图展示） */}
      {detailLocation && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 backdrop-blur-sm p-4"
          onClick={() => setDetailLocation(null)}
        >
          <div
            className="bg-paper rounded-2xl shadow-2xl border border-line w-full max-w-lg max-h-[85vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            {/* 弹窗头部 */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-line/60">
              <div className="flex items-center gap-2 min-w-0">
                <MapPin size={18} className="text-lake flex-shrink-0" />
                <h3 className="font-display font-bold text-lg text-ink truncate">
                  {detailLocation.name}
                </h3>
                {detailLocation.is_verified ? (
                  <Badge variant="success">已核验</Badge>
                ) : (
                  <Badge variant="warning">待核验</Badge>
                )}
              </div>
              <button
                onClick={() => setDetailLocation(null)}
                className="w-8 h-8 rounded-full flex items-center justify-center text-ink-sub hover:bg-mist transition-colors flex-shrink-0"
                aria-label="关闭"
              >
                <X size={16} />
              </button>
            </div>

            {/* 弹窗内容 */}
            <div className="px-5 py-4 space-y-4">
              {/* 地点信息 */}
              <div className="grid grid-cols-2 gap-3 text-sm">
                {detailLocation.building && (
                  <div className="flex items-center gap-2">
                    <Building2 size={14} className="text-ink-muted flex-shrink-0" />
                    <span className="text-ink-muted">建筑：</span>
                    <span className="text-ink">{detailLocation.building}</span>
                  </div>
                )}
                {detailLocation.floor && (
                  <div className="flex items-center gap-2">
                    <Layers size={14} className="text-ink-muted flex-shrink-0" />
                    <span className="text-ink-muted">楼层：</span>
                    <span className="text-ink">{detailLocation.floor}</span>
                  </div>
                )}
                <div className="flex items-center gap-2">
                  <span className="text-ink-muted">关联帖子：</span>
                  <span className="text-ink font-medium">{detailLocation.post_count} 条</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-ink-muted">创建时间：</span>
                  <span className="text-ink text-xs">{formatDate(detailLocation.created_at)}</span>
                </div>
              </div>

              {/* 描述 */}
              {detailLocation.description && (
                <div className="text-sm text-ink-sub bg-mist/60 rounded-md px-3 py-2 border border-line/60">
                  {detailLocation.description}
                </div>
              )}

              {/* 地图展示 */}
              <div>
                <div className="text-xs font-semibold text-ink-muted uppercase tracking-wider mb-2">
                  地图位置
                </div>
                <MapLocationPicker
                  key={detailLocation.id}
                  initialLat={detailLocation.latitude}
                  initialLng={detailLocation.longitude}
                  initialName={detailLocation.name}
                  readOnly
                  height={280}
                />
              </div>

              {/* 操作按钮 */}
              <div className="flex gap-2 pt-2">
                {detailLocation.is_verified ? (
                  <Button
                    variant="secondary"
                    className="flex-1"
                    loading={actingId === detailLocation.id}
                    onClick={() => {
                      void handleVerify(detailLocation, false);
                      setDetailLocation(null);
                    }}
                  >
                    <X size={14} className="mr-1" />
                    取消核验
                  </Button>
                ) : (
                  <Button
                    variant="primary"
                    className="flex-1"
                    loading={actingId === detailLocation.id}
                    onClick={() => {
                      void handleVerify(detailLocation, true);
                      setDetailLocation(null);
                    }}
                  >
                    <Check size={14} className="mr-1" />
                    核验通过
                  </Button>
                )}
                <Button variant="text" onClick={() => setDetailLocation(null)}>
                  关闭
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AdminLocationsPage;

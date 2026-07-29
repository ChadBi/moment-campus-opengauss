import React, { useEffect, useState, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Card } from '../../components/ui/Card';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import {
  platformApi,
  type SchoolListResponse,
} from '../../services/platform';
import { useUIStore } from '../../store/useUIStore';
import { useAuthStore } from '../../store/useAuthStore';
import type {
  ImportPreviewResult,
  ImportCommitResult,
  ImportRowError,
} from '../../types';
import {
  Upload,
  Download,
  FileText,
  AlertCircle,
  CheckCircle,
  Eye,
  Send,
  RefreshCw,
  MapPin,
  FileEdit,
} from 'lucide-react';

/** 简易 CSV 解析（支持引号包裹与逗号转义） */
const parseCSV = (text: string): Array<Record<string, string>> => {
  const lines = text.replace(/\r\n/g, '\n').replace(/\r/g, '\n').split('\n');
  if (lines.length < 2) return [];
  const headers = parseCSVLine(lines[0]);
  const rows: Array<Record<string, string>> = [];
  for (let i = 1; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line) continue;
    const values = parseCSVLine(line);
    const row: Record<string, string> = {};
    headers.forEach((h, idx) => {
      row[h] = values[idx] || '';
    });
    rows.push(row);
  }
  return rows;
};

const parseCSVLine = (line: string): string[] => {
  const result: string[] = [];
  let current = '';
  let inQuotes = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (ch === '"') {
      if (inQuotes && line[i + 1] === '"') {
        current += '"';
        i++;
      } else {
        inQuotes = !inQuotes;
      }
    } else if (ch === ',' && !inQuotes) {
      result.push(current);
      current = '';
    } else {
      current += ch;
    }
  }
  result.push(current);
  return result;
};

/** 将 CSV 行的字符串值转为后端期望的类型 */
const normalizeRows = (
  rows: Array<Record<string, string>>
): Array<Record<string, unknown>> => {
  return rows.map((row) => {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(row)) {
      const trimmed = v.trim();
      if (trimmed === '') {
        out[k] = null;
      } else if (
        k === 'latitude' ||
        k === 'longitude'
      ) {
        out[k] = parseFloat(trimmed);
      } else if (k === 'is_anonymous') {
        out[k] = trimmed === 'true' || trimmed === '1';
      } else if (k === 'location_ref') {
        const n = parseInt(trimmed, 10);
        out[k] = Number.isNaN(n) ? trimmed : n;
      } else {
        out[k] = trimmed;
      }
    }
    return out;
  });
};

const SchoolImportPage: React.FC = () => {
  const { user } = useAuthStore();
  const isSuperAdmin = user?.role === 'super_admin';
  const showToast = useUIStore((s) => s.showToast);
  const [searchParams] = useSearchParams();

  const [schools, setSchools] = useState<SchoolListResponse | null>(null);
  const [selectedSchoolId, setSelectedSchoolId] = useState<number | null>(
    searchParams.get('school_id')
      ? parseInt(searchParams.get('school_id')!, 10)
      : null
  );
  const [loading, setLoading] = useState(true);

  // 文件/数据
  const [fileName, setFileName] = useState<string>('');
  const [rawRows, setRawRows] = useState<Array<Record<string, unknown>>>([]);
  const [parsing, setParsing] = useState(false);

  // 预览/提交结果
  const [previewResult, setPreviewResult] =
    useState<ImportPreviewResult | null>(null);
  const [commitResult, setCommitResult] =
    useState<ImportCommitResult | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const loadData = useCallback(async () => {
    try {
      const data = await platformApi.listSchools({
        page: 1,
        page_size: 100,
      });
      setSchools(data);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : '加载学校列表失败';
      showToast(message, 'error');
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadData();
  }, [loadData]);

  /** 下载模板 */
  const handleDownloadTemplate = async () => {
    try {
      const blob = await platformApi.downloadImportTemplate();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'school-import-template.csv';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      showToast('模板已下载', 'success');
    } catch (err) {
      const message = err instanceof Error ? err.message : '下载失败';
      showToast(message, 'error');
    }
  };

  /** 处理文件上传 */
  const handleFileUpload = async (
    e: React.ChangeEvent<HTMLInputElement>
  ) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setParsing(true);
    setPreviewResult(null);
    setCommitResult(null);
    try {
      const text = await file.text();
      const csvRows = parseCSV(text);
      if (csvRows.length === 0) {
        showToast('CSV 文件为空或格式错误', 'error');
        return;
      }
      const normalized = normalizeRows(csvRows);
      setRawRows(normalized);
      setFileName(file.name);
      showToast(`已解析 ${normalized.length} 行数据`, 'success');
    } catch (err) {
      const message = err instanceof Error ? err.message : '文件解析失败';
      showToast(message, 'error');
    } finally {
      setParsing(false);
    }
  };

  /** 预览（dry_run） */
  const handlePreview = async () => {
    if (!selectedSchoolId) {
      showToast('请选择目标学校', 'error');
      return;
    }
    if (rawRows.length === 0) {
      showToast('请先上传 CSV 文件', 'error');
      return;
    }
    setSubmitting(true);
    setPreviewResult(null);
    setCommitResult(null);
    try {
      const resp = await platformApi.importSchoolData(
        selectedSchoolId,
        { rows: rawRows },
        true
      );
      if (resp.mode === 'preview') {
        setPreviewResult(resp.result as ImportPreviewResult);
        showToast(
          (resp.result as ImportPreviewResult).valid
            ? '预览通过，可以提交'
            : `预览发现 ${(resp.result as ImportPreviewResult).errors.length} 个错误`,
          (resp.result as ImportPreviewResult).valid ? 'success' : 'warning'
        );
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : '预览失败';
      showToast(message, 'error');
    } finally {
      setSubmitting(false);
    }
  };

  /** 提交（commit） */
  const handleCommit = async () => {
    if (!selectedSchoolId || !previewResult?.valid) {
      showToast('请先预览并确保无错误', 'error');
      return;
    }
    setSubmitting(true);
    setCommitResult(null);
    try {
      const resp = await platformApi.importSchoolData(
        selectedSchoolId,
        { rows: rawRows },
        false
      );
      if (resp.mode === 'commit') {
        setCommitResult(resp.result as ImportCommitResult);
        showToast('批量导入成功', 'success');
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : '提交失败';
      showToast(message, 'error');
    } finally {
      setSubmitting(false);
    }
  };

  /** 重置 */
  const handleReset = () => {
    setFileName('');
    setRawRows([]);
    setPreviewResult(null);
    setCommitResult(null);
  };

  if (!isSuperAdmin) {
    return (
      <div className="py-16 text-center">
        <p className="text-ink-sub">仅超级管理员可访问开通向导</p>
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

  return (
    <div className="space-y-6">
      {/* 页面标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-ink">开通向导</h1>
          <p className="text-ink-sub text-sm mt-1">
            下载模板 → 上传 CSV → 预览校验 → 批量导入地点与首批内容
          </p>
        </div>
        <Button
          variant="secondary"
          size="sm"
          icon={<Download size={14} />}
          onClick={handleDownloadTemplate}
        >
          下载模板
        </Button>
      </div>

      {/* 步骤 1：选择学校 */}
      <Card variant="outlined" padding="md">
        <div className="flex items-center gap-2 mb-3">
          <span className="w-6 h-6 rounded-full bg-lake text-paper text-sm font-bold grid place-items-center">
            1
          </span>
          <h2 className="text-base font-semibold text-ink">选择目标学校</h2>
        </div>
        <select
          value={selectedSchoolId ?? ''}
          onChange={(e) =>
            setSelectedSchoolId(
              e.target.value ? parseInt(e.target.value, 10) : null
            )
          }
          className="w-full md:w-80 h-10 px-3.5 bg-paper border border-line rounded-[10px] text-sm text-ink focus:outline-none focus:border-lake"
        >
          <option value="">请选择学校</option>
          {schools?.items.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}（{s.code}）
            </option>
          ))}
        </select>
        <p className="text-xs text-ink-muted mt-2">
          导入数据将强制绑定所选学校，请求体中的 school_id 字段会被忽略。
        </p>
      </Card>

      {/* 步骤 2：上传 CSV */}
      <Card variant="outlined" padding="md">
        <div className="flex items-center gap-2 mb-3">
          <span className="w-6 h-6 rounded-full bg-lake text-paper text-sm font-bold grid place-items-center">
            2
          </span>
          <h2 className="text-base font-semibold text-ink">上传 CSV 文件</h2>
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          <label className="inline-flex items-center gap-2 h-10 px-5 bg-paper-hover text-lake rounded-[10px] text-sm font-medium cursor-pointer hover:bg-line transition-colors">
            <Upload size={16} />
            <span>选择文件</span>
            <input
              type="file"
              accept=".csv,text/csv"
              className="hidden"
              onChange={handleFileUpload}
              disabled={parsing}
            />
          </label>
          {fileName && (
            <div className="flex items-center gap-2 text-sm text-ink-sub">
              <FileText size={16} className="text-lake" />
              <span>{fileName}</span>
              <Badge variant="info">{rawRows.length} 行</Badge>
              <button
                onClick={handleReset}
                className="text-danger hover:underline text-xs ml-1"
              >
                清除
              </button>
            </div>
          )}
          {parsing && (
            <div className="flex items-center gap-2 text-sm text-ink-muted">
              <RefreshCw size={14} className="animate-spin" />
              <span>解析中...</span>
            </div>
          )}
        </div>
        <p className="text-xs text-ink-muted mt-2">
          CSV 首行须为表头：type,name,description,latitude,longitude,floor,building,title,content,category_code,post_type_code,location_ref,expire_at,is_anonymous,contact_info
          ；latitude/longitude 必须使用 GCJ-02（高德坐标）。
        </p>
      </Card>

      {/* 步骤 3：预览 */}
      <Card variant="outlined" padding="md">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <span className="w-6 h-6 rounded-full bg-lake text-paper text-sm font-bold grid place-items-center">
              3
            </span>
            <h2 className="text-base font-semibold text-ink">预览校验</h2>
          </div>
          <Button
            variant="secondary"
            size="sm"
            icon={<Eye size={14} />}
            loading={submitting && !previewResult}
            disabled={!selectedSchoolId || rawRows.length === 0}
            onClick={handlePreview}
          >
            预览
          </Button>
        </div>

        {previewResult ? (
          <div className="space-y-3">
            {/* 预览摘要 */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="p-3 rounded-lg bg-paper-hover">
                <p className="text-xs text-ink-muted">总行数</p>
                <p className="text-xl font-bold text-ink">
                  {previewResult.total_rows}
                </p>
              </div>
              <div className="p-3 rounded-lg bg-lake/10">
                <p className="text-xs text-ink-muted">地点</p>
                <p className="text-xl font-bold text-lake">
                  {previewResult.locations_count}
                </p>
              </div>
              <div className="p-3 rounded-lg bg-grass/10">
                <p className="text-xs text-ink-muted">帖子</p>
                <p className="text-xl font-bold text-grass">
                  {previewResult.posts_count}
                </p>
              </div>
              <div
                className={`p-3 rounded-lg ${
                  previewResult.valid
                    ? 'bg-grass/10'
                    : 'bg-danger/10'
                }`}
              >
                <p className="text-xs text-ink-muted">状态</p>
                <p
                  className={`text-xl font-bold flex items-center gap-1 ${
                    previewResult.valid
                      ? 'text-grass'
                      : 'text-danger'
                  }`}
                >
                  {previewResult.valid ? (
                    <>
                      <CheckCircle size={18} /> 通过
                    </>
                  ) : (
                    <>
                      <AlertCircle size={18} /> {previewResult.errors.length} 错误
                    </>
                  )}
                </p>
              </div>
            </div>

            {/* 错误列表 */}
            {previewResult.errors.length > 0 && (
              <div>
                <h4 className="text-sm font-semibold text-danger mb-2 flex items-center gap-1.5">
                  <AlertCircle size={16} />
                  错误详情
                </h4>
                <div className="max-h-48 overflow-y-auto space-y-1">
                  {previewResult.errors.map((err: ImportRowError, idx) => (
                    <div
                      key={idx}
                      className="flex items-center gap-2 text-xs p-2 rounded-lg bg-danger/5"
                    >
                      <Badge variant="danger" className="shrink-0">
                        行 {err.row_index}
                      </Badge>
                      <span className="text-ink font-medium">
                        {err.field}
                      </span>
                      <span className="text-ink-muted">{err.message}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* 地点预览 */}
            {previewResult.locations.length > 0 && (
              <div>
                <h4 className="text-sm font-semibold text-ink mb-2 flex items-center gap-1.5">
                  <MapPin size={16} className="text-lake" />
                  地点预览（{previewResult.locations.length}）
                </h4>
                <div className="max-h-40 overflow-y-auto">
                  <table className="w-full text-xs">
                    <thead className="text-ink-muted">
                      <tr className="border-b border-line">
                        <th className="py-1.5 px-2 text-left font-medium">行</th>
                        <th className="py-1.5 px-2 text-left font-medium">名称</th>
                        <th className="py-1.5 px-2 text-left font-medium">经纬度</th>
                        <th className="py-1.5 px-2 text-left font-medium">楼层</th>
                      </tr>
                    </thead>
                    <tbody>
                      {previewResult.locations.map((loc) => (
                        <tr
                          key={loc.row_index}
                          className="border-b border-line/30"
                        >
                          <td className="py-1.5 px-2 text-ink-muted">
                            {loc.row_index}
                          </td>
                          <td className="py-1.5 px-2 text-ink">
                            {loc.name}
                          </td>
                          <td className="py-1.5 px-2 text-ink-sub">
                            GCJ-02：{loc.latitude.toFixed(4)},{loc.longitude.toFixed(4)}
                          </td>
                          <td className="py-1.5 px-2 text-ink-sub">
                            {loc.floor || '-'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* 帖子预览 */}
            {previewResult.posts.length > 0 && (
              <div>
                <h4 className="text-sm font-semibold text-ink mb-2 flex items-center gap-1.5">
                  <FileEdit size={16} className="text-grass" />
                  帖子预览（{previewResult.posts.length}）
                </h4>
                <div className="max-h-40 overflow-y-auto space-y-1">
                  {previewResult.posts.map((post) => (
                    <div
                      key={post.row_index}
                      className="flex items-center gap-2 text-xs p-2 rounded-lg bg-paper-hover"
                    >
                      <Badge variant="info" className="shrink-0">
                        行 {post.row_index}
                      </Badge>
                      <span className="text-ink font-medium truncate">
                        {post.title}
                      </span>
                      <Badge variant="default" className="shrink-0">
                        {post.category_code}
                      </Badge>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <p className="text-sm text-ink-muted text-center py-4">
            点击"预览"按钮校验数据（不写库）
          </p>
        )}
      </Card>

      {/* 步骤 4：提交 */}
      <Card variant="outlined" padding="md">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <span className="w-6 h-6 rounded-full bg-lake text-paper text-sm font-bold grid place-items-center">
              4
            </span>
            <h2 className="text-base font-semibold text-ink">批量导入</h2>
          </div>
          <Button
            variant="primary"
            size="sm"
            icon={<Send size={14} />}
            loading={submitting && !commitResult}
            disabled={!previewResult?.valid}
            onClick={handleCommit}
          >
            提交导入
          </Button>
        </div>

        {commitResult ? (
          <div className="space-y-3">
            <div className="flex items-center gap-2 p-3 rounded-lg bg-grass/10 text-grass">
              <CheckCircle size={20} />
              <div>
                <p className="font-semibold">导入成功</p>
                <p className="text-xs text-ink-muted">
                  批次 ID：{commitResult.batch_id}
                </p>
              </div>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div className="p-3 rounded-lg bg-lake/10 text-center">
                <p className="text-xs text-ink-muted">地点创建</p>
                <p className="text-2xl font-bold text-lake">
                  {commitResult.locations_created}
                </p>
              </div>
              <div className="p-3 rounded-lg bg-grass/10 text-center">
                <p className="text-xs text-ink-muted">帖子创建</p>
                <p className="text-2xl font-bold text-grass">
                  {commitResult.posts_created}
                </p>
              </div>
              <div className="p-3 rounded-lg bg-info/10 text-center">
                <p className="text-xs text-ink-muted">总计</p>
                <p className="text-2xl font-bold text-info">
                  {commitResult.total_created}
                </p>
              </div>
            </div>
            {commitResult.errors.length > 0 && (
              <div className="text-xs text-danger">
                注：提交阶段有 {commitResult.errors.length} 个错误（整批已回滚）
              </div>
            )}
            <Button
              variant="secondary"
              size="sm"
              icon={<RefreshCw size={14} />}
              onClick={handleReset}
            >
              重新导入
            </Button>
          </div>
        ) : (
          <p className="text-sm text-ink-muted text-center py-4">
            {previewResult?.valid
              ? '点击"提交导入"执行批量写入（事务保护，任一行失败整批回滚）'
              : '请先完成预览并确保无错误'}
          </p>
        )}
      </Card>
    </div>
  );
};

export default SchoolImportPage;

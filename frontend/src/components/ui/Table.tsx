import React from 'react';
import { ChevronLeft, ChevronRight, Inbox } from 'lucide-react';

// ============ 类型定义 ============

export interface Column<T> {
  /** 列标识，对应数据字段名 */
  key: string;
  /** 列标题 */
  title: string;
  /** 列宽 */
  width?: string | number;
  /** 自定义渲染 */
  render?: (value: any, row: T, index: number) => React.ReactNode;
  /** 对齐方式 */
  align?: 'left' | 'center' | 'right';
  /** 是否固定列宽不换行 */
  nowrap?: boolean;
}

interface TableProps<T> {
  /** 列配置 */
  columns: Column<T>[];
  /** 数据源 */
  data: T[];
  /** 行 key 字段名或提取函数，默认 'id' */
  rowKey?: string | ((row: T) => string | number);
  /** 加载中 */
  loading?: boolean;
  /** 是否支持行选择 */
  selectable?: boolean;
  /** 当前选中的行 key 列表 */
  selectedRowKeys?: Array<string | number>;
  /** 选择变化回调 */
  onSelectionChange?: (selectedKeys: Array<string | number>) => void;
  /** 空数据提示文案 */
  emptyText?: string;
  /** 自定义类名 */
  className?: string;
}

// ============ 辅助函数 ============

const getRowKey = <T,>(row: T, rowKey: TableProps<T>['rowKey']): string | number => {
  if (typeof rowKey === 'function') {
    return rowKey(row);
  }
  const field = rowKey || 'id';
  return (row as any)[field];
};

const alignClass = (align?: 'left' | 'center' | 'right'): string => {
  if (align === 'center') return 'text-center';
  if (align === 'right') return 'text-right';
  return 'text-left';
};

// ============ Table 组件（泛型） ============

export function Table<T extends Record<string, any>>({
  columns,
  data,
  rowKey = 'id',
  loading = false,
  selectable = false,
  selectedRowKeys = [],
  onSelectionChange,
  emptyText = '暂无数据',
  className = '',
}: TableProps<T>) {
  const allKeys = data.map((row) => getRowKey(row, rowKey));
  const allChecked = selectable && data.length > 0 && allKeys.every((k) => selectedRowKeys.includes(k));
  const indeterminate = selectable && !allChecked && allKeys.some((k) => selectedRowKeys.includes(k));

  /** 全选/取消全选 */
  const handleSelectAll = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!onSelectionChange) return;
    if (e.target.checked) {
      onSelectionChange(allKeys);
    } else {
      onSelectionChange([]);
    }
  };

  /** 单行选择切换 */
  const handleRowSelect = (key: string | number, checked: boolean) => {
    if (!onSelectionChange) return;
    if (checked) {
      onSelectionChange([...selectedRowKeys, key]);
    } else {
      onSelectionChange(selectedRowKeys.filter((k) => k !== key));
    }
  };

  return (
    <div className={`bg-paper border border-line rounded-md overflow-hidden ${className}`}>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          {/* 表头 */}
          <thead>
            <tr className="bg-mist/60 border-b border-line">
              {selectable && (
                <th className="px-4 py-3 w-12 text-left">
                  <input
                    type="checkbox"
                    checked={allChecked}
                    ref={(el) => {
                      if (el) el.indeterminate = indeterminate;
                    }}
                    onChange={handleSelectAll}
                    className="w-4 h-4 rounded border-line text-lake focus:ring-lake/30 cursor-pointer"
                  />
                </th>
              )}
              {columns.map((col) => (
                <th
                  key={col.key}
                  className={`px-4 py-3 font-semibold text-ink-sub ${alignClass(col.align)} ${col.nowrap ? 'whitespace-nowrap' : ''}`}
                  style={col.width ? { width: typeof col.width === 'number' ? `${col.width}px` : col.width } : undefined}
                >
                  {col.title}
                </th>
              ))}
            </tr>
          </thead>

          {/* 表体 */}
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={columns.length + (selectable ? 1 : 0)} className="px-4 py-12 text-center text-ink-muted">
                  <div className="flex items-center justify-center gap-2">
                    <div className="w-4 h-4 border-2 border-lake/30 border-t-lake rounded-full animate-spin" />
                    <span>加载中...</span>
                  </div>
                </td>
              </tr>
            ) : data.length === 0 ? (
              <tr>
                <td colSpan={columns.length + (selectable ? 1 : 0)} className="px-4 py-12 text-center text-ink-muted">
                  <div className="flex flex-col items-center gap-2">
                    <Inbox size={32} className="text-ink-muted/50" />
                    <span>{emptyText}</span>
                  </div>
                </td>
              </tr>
            ) : (
              data.map((row, index) => {
                const key = getRowKey(row, rowKey);
                const checked = selectedRowKeys.includes(key);
                return (
                  <tr
                    key={key}
                    className={`border-b border-line/60 transition-colors ${
                      checked ? 'bg-lake/5' : index % 2 === 1 ? 'bg-mist/30' : 'bg-paper'
                    } hover:bg-mist/50`}
                  >
                    {selectable && (
                      <td className="px-4 py-3 w-12">
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={(e) => handleRowSelect(key, e.target.checked)}
                          className="w-4 h-4 rounded border-line text-lake focus:ring-lake/30 cursor-pointer"
                        />
                      </td>
                    )}
                    {columns.map((col) => {
                      const value = (row as any)[col.key];
                      const content = col.render ? col.render(value, row, index) : value;
                      return (
                        <td
                          key={col.key}
                          className={`px-4 py-3 text-ink ${alignClass(col.align)} ${col.nowrap ? 'whitespace-nowrap' : ''}`}
                        >
                          {content ?? <span className="text-ink-muted">—</span>}
                        </td>
                      );
                    })}
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ============ 分页组件 ============

interface PaginationProps {
  page: number;
  pageSize: number;
  total: number;
  totalPages: number;
  onChange: (page: number) => void;
}

export function Pagination({ page, pageSize, total, totalPages, onChange }: PaginationProps) {
  if (total === 0) return null;

  const start = (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, total);

  return (
    <div className="flex items-center justify-between px-1 py-3 text-sm">
      <span className="text-ink-muted">
        共 <span className="text-ink font-medium">{total}</span> 条，显示 {start}-{end}
      </span>
      <div className="flex items-center gap-1">
        <button
          onClick={() => onChange(page - 1)}
          disabled={page <= 1}
          className="p-1.5 rounded-md border border-line text-ink-sub hover:bg-mist disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          aria-label="上一页"
        >
          <ChevronLeft size={16} />
        </button>
        <span className="px-3 py-1 text-ink">
          {page} / {totalPages || 1}
        </span>
        <button
          onClick={() => onChange(page + 1)}
          disabled={page >= totalPages}
          className="p-1.5 rounded-md border border-line text-ink-sub hover:bg-mist disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          aria-label="下一页"
        >
          <ChevronRight size={16} />
        </button>
      </div>
    </div>
  );
}

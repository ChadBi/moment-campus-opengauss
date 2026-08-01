# 任务报告：运行时 Analytics 废弃问题报告指标清理

## 1. 任务概述

采用 TDD 清理运行时 Analytics 中已随 `post_change_reports` 删除而失效的指标与文案，覆盖后端接口说明、前端类型、平台概览页和校级分析页，同时保留普通举报指标的现行语义。

## 2. 已完成内容

- 新增运行时 Analytics 契约回归测试，约束废弃字段与“问题报告”文案不得重新进入指定运行时代码。
- 移除 `open_change_reports`、`avg_change_report_handle_seconds`、`change_reports_handled_count` 前端类型引用。
- 移除平台概览页的“问题报告”统计和校级分析页的问题报告 SLA 卡片。
- 更新后端 Analytics 接口和治理 SLA 说明，不再宣称读取 `post_change_reports` 或计算问题报告处理时长。
- 保留 `avg_report_handle_seconds`、`reports_handled_count`、待处理举报数以及“举报创建 → 处理完成”等普通举报语义。

## 3. 未完成内容

暂无。

## 4. 实现思路

先编写静态契约回归测试，扫描后端 Analytics 运行时接口/服务、前端 Analytics 与平台类型及两个展示页面。RED 阶段确认测试准确检出 12 处废弃契约；随后仅清理目标字段和文案，并通过独立断言保护普通举报字段与页面语义，完成 GREEN。未修改已正确仅返回审核和普通举报指标的后端计算逻辑。

## 5. 修改文件

- `backend/tests/test_analytics_removed_metrics_contract.py`
- `backend/app/api/analytics.py`
- `backend/app/services/analytics_service.py`
- `frontend/src/services/analytics.ts`
- `frontend/src/services/admin.ts`
- `frontend/src/pages/admin/AnalyticsPage.tsx`
- `frontend/src/pages/admin/PlatformOverviewPage.tsx`
- `AIwork/运行时Analytics废弃问题报告指标清理任务报告.md`

## 6. 影响范围

影响校级 Analytics 接口说明、治理 SLA 前端契约与展示，以及平台首页内容治理摘要。普通举报后端统计口径、平台待处理举报数、审核 SLA、Analytics API 路径和权限均不变；未修改小程序、`TODO.md` 和数据库。

## 7. 测试与验证

- RED：`pytest tests/test_analytics_removed_metrics_contract.py -v`，结果 1 failed / 1 passed；失败按预期列出 12 处废弃契约。
- GREEN：同一测试结果 2 passed。
- 相关后端回归：`pytest tests/test_analytics_metrics.py tests/test_adm01_admin_workbench.py tests/test_analytics_removed_metrics_contract.py -v`，结果 41 passed。
- 前端 Lint：`npm run lint`，通过，无错误输出。
- 前端构建：`npm run build`，通过；Vite 仅报告既有的大 chunk 警告。
- VS Code 诊断：无诊断项。
- 综合变更完成后执行全量 Playwright E2E，结果 38 passed、0 failed、0 skipped，覆盖管理员后台、平台管理、旧治理入口兼容和其他关键链路。

## 8. 后续建议

继续以 `test_analytics_removed_metrics_contract.py` 约束后端与前端运行时代码，防止已删除的问题报告指标重新进入 Analytics 契约。

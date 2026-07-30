# 任务报告：docs 目录系统性整理与校对

## 1. 任务概述

对 `docs/` 目录下的所有设计文档进行系统性整理与校对，修正文档中与当前代码实现不一致的内容，确保文档的准确性和完整性。以当前代码为唯一标准，移除已废弃的实体引用（PostType、Tag、Favorite）、更新状态机描述为 6 态、更新协同验证为 5 类、更新数据库引用为 openGauss。

## 2. 已完成内容

- 完成 16 份核心设计文档的校对与修正
- 移除所有 PostType（信息类型）模型引用
- 移除所有 Tag（标签）和 PostTag 模型引用
- 移除所有 Favorite（收藏）功能引用
- 将 5 类协同验证（confirmation/refutation/update/expiration_report/conflict_report）写入文档
- 将 6 态状态机（draft/pending/published/expired/conflict/archived）写入文档
- 将数据库引用从 SQLite/PostgreSQL 统一修正为 openGauss 7.0
- 更新分类设计为当前 5 个核心分类
- 修正权限矩阵为 user < admin < super_admin 三级
- 保留历史文档（docs/18-35+）原貌，作为迁移记录

## 3. 未完成内容

暂无

## 4. 实现思路

1. **以代码为唯一标准**：通过阅读 `backend/app/core/post_status.py`、`backend/app/core/validation_type.py`、`backend/app/config.py`、`backend/scripts/seed_data.py` 等核心文件，确认当前实际实现。
2. **逐文档排查**：使用 Grep 工具搜索过时关键词（PostType、Tag、Favorite、收藏、SQLite、PostgreSQL），精确定位需要修改的位置。
3. **精准编辑**：使用 Edit 工具进行最小化修改，保持文档结构和格式完整性。
4. **批量处理**：将多个文档的修复任务委托给子代理并行执行，提高效率。
5. **保留历史**：对 docs/18-35+ 等历史迁移文档保持原样，仅修正当前活跃设计文档（00-17）。

## 5. 修改文件

| 文件 | 修改内容 |
|------|----------|
| docs/00_project_overview.md | 产品边界、社区验证类型、状态机描述 |
| docs/01_product_requirements.md | 权限矩阵、验证类型、状态机、技术约束 |
| docs/02_user_roles_and_scenarios.md | 移除收藏、Tag 引用 |
| docs/03_feature_scope_and_priority.md | 移除收藏功能章节和引用 |
| docs/04_information_architecture.md | 移除"我的收藏"页面和导航 |
| docs/05_user_flows.md | F08/F17 流程重写，移除收藏和 Tag |
| docs/06_page_specifications.md | 移除收藏页、标签管理页 |
| docs/07_content_and_category_design.md | 分类体系重写为 5 分类，移除 PostType |
| docs/08_community_governance.md | 状态机 6 态重写，协同验证 5 类 |
| docs/10_ui_ux_design_system.md | 移除收藏图标和空状态 |
| docs/11_technical_architecture.md | 数据库方案改为 openGauss 7.0 |
| docs/12_database_design.md | 移除 PostType/Tag/Favorite 实体 |
| docs/13_api_specification.md | 移除收藏 API 模块 |
| docs/14_security_and_privacy.md | 移除收藏相关权限 |
| docs/15_testing_and_acceptance.md | 移除收藏测试场景 |
| docs/16_development_roadmap.md | 移除收藏开发任务 |

## 6. 影响范围

- 仅修改文档，不涉及任何代码变更
- 所有修改均为文档内容的准确性修正
- 历史文档（18-35+）未受影响

## 7. 测试与验证

本次任务为文档校对工作，无需运行代码测试。

验证方式：
1. 使用 Grep 搜索残留的过时关键词，确认已全部清理
2. 对比核心源码文件，确认文档描述与代码实现一致
3. 交叉检查文档间的一致性（如状态机描述在多处保持统一）

## 8. 后续建议

1. 可考虑为 docs/ 目录建立自动化文档检查脚本，定期检测过时引用
2. docs/design/ 下的 ER 图源文件（.dot）和图片（.png）也需要同步更新
3. docs/24-35 等需求分析和数据库设计文档中的过时引用可在后续任务中处理
4. 项目根目录的两个早期演示 HTML 文件应考虑清理或归档

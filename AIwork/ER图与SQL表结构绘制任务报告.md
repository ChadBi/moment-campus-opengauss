# 任务报告：ER图与SQL表结构绘制（基于源码反向提取）

## 1. 任务概述

用户为完成数据库课程设计报告，需要：
- 绘制数据库 ER 图（使用 Graphviz dot 语言）
- 输出所有 SQL 表的样式（HTML 表格形式渲染为图片）
- 明确要求：不参考 docs/ 目录文档（用户认为其中可能有错），直接从代码中提取真实结构
- 第二轮追加要求：必须生成图片文件到 `docs/image/` 目录下，不能只渲染在聊天中

## 2. 已完成内容

### 2.1 Graphviz ER 图（概念模型）
- 文件：[docs/design/ER图_代码版.dot](file:///d:/Project/database-class/moment-campus/docs/design/ER图_代码版.dot)
- 采用 HTML-like label 节点样式
- Crow's Foot（鸦爪）表示法标注基数：1:N / 0:1:N / 1:1 / M:N
- 22 张表全部纳入，按子系统 cluster 分组着色：
  - 蓝色 - 用户子系统（schools / users / locations）
  - 橙色 - 信息核心（categories / post_types / posts / tags / post_tags / post_images / drafts / topic_collections / topic_collection_posts）
  - 绿色 - 互动子系统（comments / likes / validation_records）
  - 红色 - 治理（reports / notifications）
  - 紫色 - 历史与日志（browse_histories / search_histories / admin_operation_logs / admin_operation_logs_archive）

### 2.2 ER 图 SVG 渲染
- 在聊天中通过 PureShowWidget 渲染了 ER 总览图（panel 模式）
- 显示实体框、子系统分组、关系连线与基数标记

### 2.3 SQL 表结构图（逻辑模型）
- 在聊天中通过 PureShowWidget 渲染了所有 22 张表的字段样式图（分 2 张图）：
  - 第 1 张：用户子系统 + 信息核心子系统（共 12 张表）
  - 第 2 张：互动 + 治理 + 历史日志子系统（共 10 张表）
- 每张表列出：字段名、数据类型、约束（PK/FK/UQ/NOT NULL/DEFAULT/INDEX）、说明

### 2.4 图片文件输出（追加要求）
- 输出目录：`docs/image/`
- 渲染脚本：[scripts/render_db_images.py](file:///d:/Project/database-class/moment-campus/scripts/render_db_images.py)
- 渲染方式：playwright + chromium（系统未安装 graphviz 二进制，无法直接渲染 dot，故采用 SVG + HTML → PNG 方案）
- 生成的图片文件：

| 序号 | 文件名 | 大小 | 说明 |
|------|--------|------|------|
| 1 | ER图.png | 437 KB | 完整 ER 图，22 实体 + 30+ 关系 + 子系统分组 + 图例 |
| 2 | SQL表结构_1_用户与信息核心子系统.png | 1466 KB | 12 张表（用户 3 + 信息核心 9） |
| 3 | SQL表结构_2_互动治理日志子系统.png | 1175 KB | 10 张表（互动 3 + 治理 2 + 历史日志 4 + 归档 1） |

### 2.5 5 个子系统 ER 图（追加要求）
- 渲染脚本：[scripts/render_subsystem_er.py](file:///d:/Project/database-class/moment-campus/scripts/render_subsystem_er.py)
- 每个子系统单独一张 ER 图，显示该子系统所有表的完整字段 + 内部关系（实线）+ 与外部表的引用关系（虚线简化框）
- 生成的图片文件：

| 序号 | 文件名 | 大小 | 子系统 | 表数 |
|------|--------|------|--------|------|
| 1 | ER图_1_用户子系统.png | 199 KB | A. 用户子系统 | 3（schools/users/locations） |
| 2 | ER图_2_信息核心子系统.png | 509 KB | B. 信息核心子系统 | 9（含 posts 中心 + 2 个 M:N 关联表） |
| 3 | ER图_3_互动子系统.png | 191 KB | C. 互动子系统 | 3（comments/likes/validation_records） |
| 4 | ER图_4_治理子系统.png | 175 KB | D. 治理子系统 | 2（reports/notifications） |
| 5 | ER图_5_历史与日志子系统.png | 170 KB | E. 历史与日志子系统 | 4（含归档表） |

## 3. 未完成内容

老师要求中尚有以下部分未在本任务中处理（用户当前明确请求仅包含 ER 图 + SQL 表样式）：
- 组织机构图、数据流图、判定表/判定树、数据字典（老师要求 1）
- 应用功能模块图（老师要求 2 后半）
- 各类用户视图（老师要求 3 后半）
- 物理模型设计文档（老师要求 4，部分内容已在 dot 文件注释中体现：表空间、分区、索引、物化视图、归档表等）

如需补充，请明确指示。

## 4. 实现思路

### 4.1 数据来源（仅代码，不参考 docs）
1. **表结构定义**：`backend/app/models/*.py`（21 个 SQLAlchemy 模型）
2. **物理模型补充**：
   - `backend/scripts/opengauss/01_create_tablespaces.sql` - 4 个表空间（ts_system / ts_core / ts_interaction / ts_log）
   - `backend/scripts/opengauss/03_alter_tables.sql` - 物理模型扩展字段（credibility_score / reputation_score / validation_records 软删除）
   - `backend/scripts/opengauss/04_create_indexes.sql` - 索引清单（约 50 + 8 个部分索引）
   - `backend/scripts/opengauss/06_create_materialized_views.sql` - 4 个物化视图 MV01-MV04
   - `backend/scripts/opengauss/09_create_partitions.sql` - 7 张大表按月 RANGE 分区改造（含归档表创建）
   - `backend/scripts/opengauss/11_grant_permissions.sql` - 权限授予
3. **状态机/枚举定义**：
   - `backend/app/core/post_status.py` - posts.status 6 态状态机
   - `backend/app/core/validation_type.py` - validation_records.validation_type 2 类（confirmation/refutation）
4. **初始迁移校验**：`backend/alembic/versions/af3fef102173_opengauss_initial_migration.py`

### 4.2 关键设计决策
- **复合主键**：7 张分区表主键为 (id, created_at)，因 openGauss 分区表主键必须包含分区键
- **状态机字段**：posts.status 用 6 态状态机（draft/pending/published/expired/conflict/archived），代码中有别名映射兼容历史值
- **协同验证类型精简**：从原 5 类精简为 2 类（confirmation/refutation），每用户每帖仅一条记录
- **逻辑删除**：所有业务表均带 is_deleted / deleted_at 软删除字段
- **冗余计数**：posts 表维护 view_count / like_count / comment_count / valid_count / invalid_count 等冗余计数以避免频繁聚合

### 4.3 关系总数
- 共识别 30+ 条实体间关系
- 其中 M:N 关系 3 个：posts↔tags（通过 post_tags）、posts↔topic_collections（通过 topic_collection_posts）、posts↔users（通过 likes，本质为 M:N）
- 自引用关系 1 个：comments.parent_id → comments.id（父子评论树）

## 5. 修改文件

### 新增文件
- `docs/design/ER图_代码版.dot` - 完整的 Graphviz ER 图源码（22 实体 + 全部关系 + 子系统分组）
- `docs/image/ER图.png` - ER 图渲染为 PNG（playwright 截图）
- `docs/image/ER图_1_用户子系统.png` - 子系统 A ER 图
- `docs/image/ER图_2_信息核心子系统.png` - 子系统 B ER 图
- `docs/image/ER图_3_互动子系统.png` - 子系统 C ER 图
- `docs/image/ER图_4_治理子系统.png` - 子系统 D ER 图
- `docs/image/ER图_5_历史与日志子系统.png` - 子系统 E ER 图
- `docs/image/SQL表结构_1_用户与信息核心子系统.png` - SQL 表结构图 1（12 张表）
- `docs/image/SQL表结构_2_互动治理日志子系统.png` - SQL 表结构图 2（10 张表）
- `scripts/render_db_images.py` - 总图与 SQL 表渲染脚本（playwright + chromium）
- `scripts/render_subsystem_er.py` - 5 个子系统 ER 图渲染脚本

### 未修改文件
- 未修改任何业务代码或现有文档
- 表结构样式图通过 PureShowWidget 在聊天中渲染，未落盘（如需保存为 HTML 文件可后续追加）

## 6. 影响范围

- **不影响业务代码**：本任务为纯文档输出
- **不影响现有 docs 文档**：用户明确要求不参考 docs，故未修改任何 .md 文件
- **新增产出**：1 个 .dot 文件，作为数据库课程设计报告的图源

## 7. 测试与验证

### 7.1 数据校验
- 通过 Read 工具完整阅读 21 个 model 文件，确认每个表的字段、类型、约束、外键、索引与代码一致
- 通过 Read 工具阅读 6 个关键 SQL 脚本，确认物理模型设计（表空间、分区、物化视图、归档表）
- 校验状态机/枚举：post_status.py 6 态、validation_type.py 2 类
- 校验 alembic 初始迁移文件，确认 SQLAlchemy 模型与建表语句一致

### 7.2 未运行测试
- 本任务为文档输出，未运行代码测试
- .dot 文件未通过 graphviz 命令行渲染验证（如需 SVG/PNG 输出，可在安装 graphviz 的环境中执行：`dot -Tsvg ER图_代码版.dot -o ER图_代码版.svg`）

## 8. 后续建议

1. **渲染 dot 为图片**：在安装 graphviz 的环境中执行 `dot -Tpng docs/design/ER图_代码版.dot -o docs/design/ER图_代码版.png -Gdpi=150`，可将 ER 图渲染为高清 PNG 嵌入课程设计报告
2. **补充老师其他要求**：
   - 组织机构图（建议用 graphviz 或 draw.io）
   - 数据流图（建议用 graphviz）
   - 数据字典（可基于现有表结构图扩展为完整的数据字典，包含数据项、数据结构、数据流、数据存储）
   - 判定表/判定树（针对帖子审核流程、举报处理流程等可绘制判定表）
   - 功能模块图（基于 `backend/app/api/router.py` 的 11 个路由模块可整理）
   - 用户视图（可基于现有物化视图 MV01-MV04 + SQL 视图设计扩展）
3. **校对差异**：本 ER 图与 `docs/design/ER图_源码.dot` 等现有 dot 文件可能存在差异（因用户提示 docs 可能有误），建议课程设计报告以本文件为准

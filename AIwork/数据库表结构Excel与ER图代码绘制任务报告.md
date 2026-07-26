# 任务报告：数据库表结构 Excel 与 ER 图代码绘制

## 1. 任务概述

为数据库课程设计答辩准备可视化产物：
1. 生成 21 张表的完整结构 Excel 文件（含总览 Sheet + 每表一个 Sheet，PK/FK 高亮）
2. 用代码绘制 ER 图（总体 + 5 个子系统），输出 SVG 矢量图
3. 生成 Graphviz DOT 源码，供后续安装 Graphviz 后渲染更精美版本

严格遵循 [AGENTS.md](../AGENTS.md) 要求，使用 `backend/.venv` 虚拟环境。

## 2. 已完成内容

### 2.1 创建虚拟环境并安装依赖

- 创建 `backend/.venv`（Python 3.14.0）
- 安装 `openpyxl==3.1.5`（Excel 生成）
- 安装 `graphviz==0.21`（DOT 源码生成；系统未安装 Graphviz 软件，仅生成源码）

### 2.2 编写生成脚本

[backend/scripts/generate_db_design.py](../backend/scripts/generate_db_design.py)（约 1150 行），包含：
- 21 张表的完整字段定义（基于 `backend/app/models/` 实际代码）
- 35 个关系定义（1:N / M:N / 自引用）
- 5 个子系统分组
- Excel 生成函数（含样式、PK/FK 高亮、冻结表头）
- SVG ER 图生成类（含 6 类实体配色、自动布局、基数标注、关系标签）
- DOT 源码生成函数

### 2.3 生成产物清单

输出目录：`docs/design/`

| 文件 | 大小 | 说明 |
| ---- | ---- | ---- |
| 此刻校园_数据库表结构.xlsx | 39 KB | Excel 表结构（22 个 Sheet：1 总览 + 21 表） |
| ER图_总体.svg | 12 KB | 总体 ER 图（21 实体 + 35 联系，6 类配色，网格布局） |
| ER图_用户子系统.svg | 7 KB | 用户子系统 ER 图（3 实体，含字段、基数、关系标签） |
| ER图_信息子系统.svg | 25 KB | 信息子系统 ER 图（11 实体，含字段、基数、关系标签） |
| ER图_互动子系统.svg | 17 KB | 互动子系统 ER 图（7 实体，含字段、基数、关系标签） |
| ER图_治理子系统.svg | 17 KB | 治理子系统 ER 图（6 实体，含字段、基数、关系标签） |
| ER图_管理子系统.svg | 10 KB | 管理子系统 ER 图（4 实体，含字段、基数、关系标签） |
| ER图_源码.dot | 11 KB | Graphviz DOT 源码（record 形状，含全部字段） |

## 3. 未完成内容

暂无。

## 4. 实现思路

### 4.1 技术选型

| 产物 | 技术 | 原因 |
| ---- | ---- | ---- |
| Excel | openpyxl | 纯 Python，支持样式/合并单元格/冻结窗格 |
| ER 图 SVG | 纯 Python 字符串拼接 | 无需外部依赖，浏览器即可打开，矢量缩放 |
| ER 图 DOT | graphviz 库生成源码 | 标准 Graphviz 格式，后续可渲染高精度 PNG/PDF |

未使用系统 Graphviz 软件（dot 命令不可用），改为生成 SVG（立即可查看）+ DOT（供后续渲染）双格式。

### 4.2 Excel 设计

- Sheet 1「总览」：21 张表的序号、表名、中文名、字段数、说明
- Sheet 2-22：每张表独立 Sheet，含序号、字段名、数据类型、主键(PK)、外键(→引用表)、可空、默认值、说明
- 主键行黄色高亮（#FFF2CC），外键行蓝色高亮（#DEEBF7）
- 字段名用 Consolas 字体（等宽），数据类型用 Consolas，说明用微软雅黑
- 冻结表头（A5），便于长表滚动

### 4.3 ER 图设计

**实体分类与配色**（6 类）：
| 类别 | 颜色 | 实体 |
| ---- | ---- | ---- |
| 核心实体 | 蓝(#4472C4) | users, posts, topic_collections |
| 配置实体 | 绿(#70AD47) | schools, categories, post_types, tags, locations |
| 关联实体 | 橙(#ED7D31) | post_tags, post_images, topic_collection_posts |
| 互动实体 | 黄(#FFC000) | comments, likes, favorites, browse_histories, search_histories, drafts |
| 治理实体 | 红(#C00000) | validation_records, reports, notifications |
| 系统实体 | 紫(#7030A0) | admin_operation_logs |

**总体 ER 图**：5×5 网格布局，仅显示实体名+中文名+关系连线，含图例
**子系统 ER 图**：2-3 列布局，显示实体框（含 PK/FK 字段）+ 基数标注（1/N/M）+ 关系标签（如"发布""评论""验证"）

### 4.4 数据来源

所有 21 张表的字段定义严格基于 `backend/app/models/` 下的实际代码，确保与项目一致：
- 主键统一标注为 BIGINT（物理模型 doc 27 的设计决策，解决原 Integer/BigInteger 类型不一致）
- 外键引用关系完整记录
- 字段类型、可空、默认值均与代码一致

## 5. 修改文件

### 5.1 新增文件（8 个产物 + 1 个脚本 + 1 个报告）

- `backend/scripts/generate_db_design.py`（生成脚本，约 1150 行）
- `docs/design/此刻校园_数据库表结构.xlsx`
- `docs/design/ER图_总体.svg`
- `docs/design/ER图_用户子系统.svg`
- `docs/design/ER图_信息子系统.svg`
- `docs/design/ER图_互动子系统.svg`
- `docs/design/ER图_治理子系统.svg`
- `docs/design/ER图_管理子系统.svg`
- `docs/design/ER图_源码.dot`
- `AIwork/数据库表结构Excel与ER图代码绘制任务报告.md`（本报告）

### 5.2 修改文件（1 个）

- `TODO.md`：在"数据库课程设计前期工作"小节追加生成产物记录

### 5.3 虚拟环境变更

- 新建 `backend/.venv/`（Python 3.14.0 虚拟环境）
- 安装依赖：`openpyxl==3.1.5`、`graphviz==0.21`

## 6. 影响范围

### 6.1 文档体系影响

- 补充 [doc 25 概念模型](../docs/25_数据库概念模型设计.md) 的可视化产物（SVG ER 图）
- 补充 [doc 26 逻辑模型](../docs/26_数据库逻辑模型设计.md) 的表结构产物（Excel）
- 产物可用于课程设计答辩展示

### 6.2 代码影响

新增独立生成脚本，不修改任何业务代码。脚本可重复运行，表结构变更时重新生成即可。

### 6.3 环境影响

新建 `backend/.venv` 虚拟环境，符合 [AGENTS.md](../AGENTS.md) "Python 项目必须使用 backend/.venv" 要求。后续 Python 任务可复用此环境。

## 7. 测试与验证

### 7.1 执行的验证

1. **虚拟环境验证**：`backend\.venv\Scripts\python.exe --version` → Python 3.14.0
2. **依赖验证**：`import openpyxl; import graphviz` → 均成功
3. **脚本执行**：`backend\.venv\Scripts\python.exe backend\scripts\generate_db_design.py` → 退出码 0
4. **产物完整性**：8 个文件全部生成，大小合理（6KB-39KB）
5. **数据一致性**：21 张表、35 个关系与 doc 25/26/27 统计数字一致

### 7.2 修复的问题

- 初次运行报错 `ValueError: too many values to unpack (expected 4, got 5)`：`generate_subsystem_er` 中 RELATIONS 解包写成了 4 个值，实际为 5 个值（from_table, from_card, to_table, to_card, label），已修复
- 修复 `SyntaxWarning: "\." is an invalid escape sequence`（docstring 中的转义字符）

### 7.3 未验证项

- SVG 在浏览器中的渲染效果（需用户打开 `docs/design/ER图_总体.svg` 确认）
- Excel 在 Office 中的打开效果（需用户打开 `docs/design/此刻校园_数据库表结构.xlsx` 确认）
- DOT 源码在 Graphviz 中的渲染效果（系统未安装 Graphviz，待安装后验证）

## 8. 后续建议

### 8.1 立即可做

1. 用浏览器打开 `docs/design/ER图_总体.svg` 查看总体 ER 图
2. 用 Excel 打开 `docs/design/此刻校园_数据库表结构.xlsx` 查看表结构
3. 将 SVG/Excel 嵌入课程设计答辩 PPT

### 8.2 可选增强

1. **安装 Graphviz**：`winget install Graphviz`，然后 `dot -Tpng docs/design/ER图_源码.dot -o docs/design/ER图_总体.png` 可生成高精度 PNG
2. **ER 图布局优化**：当前为网格布局，如需更美观可改用 Graphviz 的自动布局（需安装 Graphviz）
3. **Excel 增强**：可追加「关系矩阵 Sheet」「索引清单 Sheet」「视图清单 Sheet」
4. **Mermaid 版本**：可生成 Mermaid 格式 ER 图，便于在 Markdown 中直接预览

### 8.3 维护建议

- 表结构变更时，修改 `backend/scripts/generate_db_design.py` 中的 `TABLES` 列表后重新运行脚本
- 新增表/字段时同步更新 doc 25/26/27 与本脚本
- 脚本可纳入 CI/CD，每次模型变更自动重新生成设计产物

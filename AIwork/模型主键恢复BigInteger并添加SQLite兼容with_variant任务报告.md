# 任务报告：模型主键恢复 BigInteger 并添加 SQLite 兼容 with_variant

## 1. 任务概述

将 `backend/app/models/` 目录下 21 个模型文件的 id 主键字段定义从 `BigInteger` 改为 `BigInteger().with_variant(Integer, "sqlite")`，在保留 openGauss/PostgreSQL 下 BigInteger 主键能力的同时，为 SQLite 提供兼容性（SQLite 不支持 BigInteger 自增主键）。

## 2. 已完成内容

- 修改了全部 21 个模型文件的 id 主键字段定义，统一改为 `BigInteger().with_variant(Integer, "sqlite")`。
- 通过 Grep 验证：21 个文件均包含 `with_variant(Integer, "sqlite")`，且原 `mapped_column(BigInteger, primary_key` 写法已 0 匹配。
- 确认 21 个文件在修改前均已从 sqlalchemy 导入 `Integer`，无需补充导入。
- 所有外键字段保持 `BigInteger` 不变，未做改动。

## 3. 未完成内容

暂无

## 4. 实现思路

1. 逐个读取 21 个模型文件，确认每个文件的 id 主键行与 sqlalchemy 导入语句现状。
2. 检查发现：全部 21 个文件原本就已在 `from sqlalchemy import ...` 中导入了 `Integer`（早期已为兼容性补过导入），因此本次只需修改 id 主键这一行，无需补充导入。
3. 由于 id 主键行 `mapped_column(BigInteger, primary_key=True, autoincrement=True)` 在每个文件中唯一（外键使用 `BigInteger, ForeignKey(...)` 不会匹配），使用精确字符串替换将其改为 `mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)`。
4. 分 5 批并行执行 Edit，每批最多 5 个文件，避免超出并行调用上限。
5. 修改完成后用 Grep 进行双重校验：正向匹配 `with_variant(Integer, "sqlite")` 应为 21，反向匹配 `mapped_column(BigInteger, primary_key` 应为 0。

## 5. 修改文件

修改的文件列表（共 21 个，均位于 `backend/app/models/`）：
- admin_operation_log.py
- browse_history.py
- category.py
- comment.py
- draft.py
- favorite.py
- like.py
- location.py
- notification.py
- post.py
- post_image.py
- post_tag.py
- post_type.py
- report.py
- school.py
- search_history.py
- tag.py
- topic_collection.py
- topic_collection_post.py
- user.py
- validation_record.py

每个文件仅修改 id 主键一行，外键及其他字段未改动。

## 6. 影响范围

- 影响全部 21 个 ORM 模型的主键类型声明。
- 在 openGauss/PostgreSQL 上仍使用 BigInteger 主键（行为不变）；在 SQLite 上自动降级为 Integer，使自增主键可正常工作。
- 外键字段仍为 BigInteger，关联关系不受影响。
- 不涉及业务逻辑、API、前端改动。

## 7. 测试与验证

执行 Grep 双重校验（未运行单元测试，因本次仅为类型声明调整，且项目当前数据库为 openGauss，模型层改动不影响 openGauss 下的实际列类型）：

- `grep with_variant(Integer, "sqlite") backend/app/models/` → 21 个文件各 1 处匹配，共 21 处，符合预期。
- `grep "mapped_column(BigInteger, primary_key" backend/app/models/` → 0 匹配，符合预期。

## 8. 后续建议

- 项目当前已迁移至 openGauss，本次改动主要保留 SQLite 兼容性以备未来需要，无需立即重建数据库。
- 如后续切换回 SQLite 进行本地开发，可直接使用现有模型，无需再调整主键类型。
- 建议在切换数据库环境时，对模型层做一次导入与建表冒烟测试，确认 with_variant 在目标方言下生效。

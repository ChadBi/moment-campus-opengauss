# 回收站文件清单（rubbish/）

> 本目录用于集中存放项目清理过程中识别出的无用文件、临时文件及不再需要的资源。
> 所有文件均按原文件名保留，未做任何修改或删除，可按本 README 的记录恢复至原始位置。
>
> **移动日期**：2026-07-26
> **执行人**：AI 自动清理（按用户指令）
> **文件总数**：46 个（5 个根目录文件 + 1 个临时文件 + 13 张截图 + 27 个日志文件）

---

## 恢复说明

如需将某文件恢复到原始位置，可使用以下命令（PowerShell）：

```powershell
# 示例：恢复单个文件
git mv "rubbish/<文件名>" "<原始路径>"

# 示例：恢复未纳入版本控制的文件（如日志）
Move-Item "rubbish/logs/<文件名>" "<原始路径>" -Force
```

**注意**：
- 通过 `git mv` 移动的文件（根目录 5 个 + 截图 13 个）保留了 Git 历史，恢复时也应使用 `git mv`。
- 通过 `Move-Item` 移动的文件（日志 27 个 + xlsx_preview.txt 1 个）原本就未纳入 Git 版本控制（被 `.gitignore` 覆盖），恢复时使用普通文件移动即可。

---

## 1. 根目录早期 Demo 与过时文档（5 个，原位于项目根目录）

| 序号 | 文件名 | 原始路径 | 当前路径 | 移动方式 | 说明 |
|------|--------|----------|----------|----------|------|
| 1 | 创意文档.html | `创意文档.html` | `rubbish/创意文档.html` | git mv | 项目早期创意演示 HTML，已被正式前端取代 |
| 2 | 此刻校园_可演示Demo.html | `此刻校园_可演示Demo.html` | `rubbish/此刻校园_可演示Demo.html` | git mv | 项目早期可演示 Demo HTML，已被正式前端取代（AGENTS.md 注明为早期 Demo） |
| 3 | DEVELOPMENT_TASKS.md | `DEVELOPMENT_TASKS.md` | `rubbish/DEVELOPMENT_TASKS.md` | git mv | 早期开发任务清单（最后更新 2026-06-18），已被 `TODO.md` 完全取代 |
| 4 | 检查结果.json | `AIwork/检查结果.json` | `rubbish/检查结果.json` | git mv | 旧版自动化检查结果 JSON（39 项，6 项失败），已被最新 972 passed 测试基线取代 |
| 5 | 检查结果v2.json | `AIwork/检查结果v2.json` | `rubbish/检查结果v2.json` | git mv | 旧版自动化检查结果 JSON v2，同上 |

---

## 2. 临时预览文件（1 个，原位于 backend/）

| 序号 | 文件名 | 原始路径 | 当前路径 | 移动方式 | 说明 |
|------|--------|----------|----------|----------|------|
| 6 | xlsx_preview.txt | `backend/xlsx_preview.txt` | `rubbish/xlsx_preview.txt` | Move-Item | 临时生成的 xlsx 预览文本（含 openpyxl 缺失错误信息），已无用 |

---

## 3. 过期 E2E 截图（13 个，原位于 AIwork/screenshots/）

> 这些截图为早期 E2E 测试产物，已被 `AIwork/E2E全链路自动化测试与Bug修复汇总报告.md` 等正式任务报告取代，不再需要保留在主目录。

| 序号 | 文件名 | 原始路径 | 当前路径 | 移动方式 |
|------|--------|----------|----------|----------|
| 7 | screenshot-1783158090078.png | `AIwork/screenshots/screenshot-1783158090078.png` | `rubbish/screenshots/screenshot-1783158090078.png` | git mv |
| 8 | screenshot-1783158135482.png | `AIwork/screenshots/screenshot-1783158135482.png` | `rubbish/screenshots/screenshot-1783158135482.png` | git mv |
| 9 | screenshot-1783158155524.png | `AIwork/screenshots/screenshot-1783158155524.png` | `rubbish/screenshots/screenshot-1783158155524.png` | git mv |
| 10 | screenshot-1783158172663.png | `AIwork/screenshots/screenshot-1783158172663.png` | `rubbish/screenshots/screenshot-1783158172663.png` | git mv |
| 11 | screenshot-1783158191114.png | `AIwork/screenshots/screenshot-1783158191114.png` | `rubbish/screenshots/screenshot-1783158191114.png` | git mv |
| 12 | screenshot-1783158209011.png | `AIwork/screenshots/screenshot-1783158209011.png` | `rubbish/screenshots/screenshot-1783158209011.png` | git mv |
| 13 | screenshot-1783158245497.png | `AIwork/screenshots/screenshot-1783158245497.png` | `rubbish/screenshots/screenshot-1783158245497.png` | git mv |
| 14 | screenshot-1783158298991.png | `AIwork/screenshots/screenshot-1783158298991.png` | `rubbish/screenshots/screenshot-1783158298991.png` | git mv |
| 15 | screenshot-1783158337384.png | `AIwork/screenshots/screenshot-1783158337384.png` | `rubbish/screenshots/screenshot-1783158337384.png` | git mv |
| 16 | screenshot-1783158363158.png | `AIwork/screenshots/screenshot-1783158363158.png` | `rubbish/screenshots/screenshot-1783158363158.png` | git mv |
| 17 | screenshot-1783158384975.png | `AIwork/screenshots/screenshot-1783158384975.png` | `rubbish/screenshots/screenshot-1783158384975.png` | git mv |
| 18 | screenshot-1783158464326.png | `AIwork/screenshots/screenshot-1783158464326.png` | `rubbish/screenshots/screenshot-1783158464326.png` | git mv |
| 19 | screenshot-1783158498289.png | `AIwork/screenshots/screenshot-1783158498289.png` | `rubbish/screenshots/screenshot-1783158498289.png` | git mv |

---

## 4. 调试日志文件（27 个，原位于 backend/ 与 frontend/）

> 这些日志文件均为开发过程中的临时调试输出，原本就被 `.gitignore` 的 `*.log` 规则覆盖，未纳入版本控制。可安全删除或保留以备排查。

### 4.1 backend/ 日志（26 个）

| 序号 | 文件名 | 原始路径 | 当前路径 |
|------|--------|----------|----------|
| 20 | activation_funnel_console.log | `backend/activation_funnel_console.log` | `rubbish/logs/activation_funnel_console.log` |
| 21 | ai_search_test_full.log | `backend/ai_search_test_full.log` | `rubbish/logs/ai_search_test_full.log` |
| 22 | ai_search_test_output.log | `backend/ai_search_test_output.log` | `rubbish/logs/ai_search_test_output.log` |
| 23 | analytics_console.log | `backend/analytics_console.log` | `rubbish/logs/analytics_console.log` |
| 24 | analytics2_console.log | `backend/analytics2_console.log` | `rubbish/logs/analytics2_console.log` |
| 25 | auth_commercial_console.log | `backend/auth_commercial_console.log` | `rubbish/logs/auth_commercial_console.log` |
| 26 | batch1_console.log | `backend/batch1_console.log` | `rubbish/logs/batch1_console.log` |
| 27 | commercial_full_console.log | `backend/commercial_full_console.log` | `rubbish/logs/commercial_full_console.log` |
| 28 | dsc02_debug.log | `backend/dsc02_debug.log` | `rubbish/logs/dsc02_debug.log` |
| 29 | dsc02_fix1.log | `backend/dsc02_fix1.log` | `rubbish/logs/dsc02_fix1.log` |
| 30 | dsc02_full_run.log | `backend/dsc02_full_run.log` | `rubbish/logs/dsc02_full_run.log` |
| 31 | dsc02_full2.log | `backend/dsc02_full2.log` | `rubbish/logs/dsc02_full2.log` |
| 32 | dsc02_one_full.log | `backend/dsc02_one_full.log` | `rubbish/logs/dsc02_one_full.log` |
| 33 | dsc02_one.log | `backend/dsc02_one.log` | `rubbish/logs/dsc02_one.log` |
| 34 | dsc02_one2.log | `backend/dsc02_one2.log` | `rubbish/logs/dsc02_one2.log` |
| 35 | dsc02_one3.log | `backend/dsc02_one3.log` | `rubbish/logs/dsc02_one3.log` |
| 36 | dsc02_one4.log | `backend/dsc02_one4.log` | `rubbish/logs/dsc02_one4.log` |
| 37 | dsc02_run.log | `backend/dsc02_run.log` | `rubbish/logs/dsc02_run.log` |
| 38 | full_test_run.log | `backend/full_test_run.log` | `rubbish/logs/full_test_run.log` |
| 39 | gov_int_console.log | `backend/gov_int_console.log` | `rubbish/logs/gov_int_console.log` |
| 40 | gov_int2_console.log | `backend/gov_int2_console.log` | `rubbish/logs/gov_int2_console.log` |
| 41 | gov_isolated_console.log | `backend/gov_isolated_console.log` | `rubbish/logs/gov_isolated_console.log` |
| 42 | rel02_test_output.log | `backend/rel02_test_output.log` | `rubbish/logs/rel02_test_output.log` |
| 43 | seed_output.log | `backend/seed_output.log` | `rubbish/logs/seed_output.log` |
| 44 | seed_run.log | `backend/seed_run.log` | `rubbish/logs/seed_run.log` |
| 45 | seed_trace.log | `backend/seed_trace.log` | `rubbish/logs/seed_trace.log` |

### 4.2 frontend/ 日志（1 个）

| 序号 | 文件名 | 原始路径 | 当前路径 |
|------|--------|----------|----------|
| 46 | npm_build.log | `frontend/npm_build.log` | `rubbish/logs/npm_build.log` |

---

## 5. 清理范围说明

本次清理遵循以下原则：

1. **仅清理明确无用文件**：早期 Demo、过期检查结果、临时预览文件、过期截图、调试日志。
2. **保留 Git 历史**：所有 Git 跟踪文件均使用 `git mv` 移动，保留完整历史记录。
3. **不删除任何文件**：所有文件均移动到 `rubbish/`，未执行删除操作，可随时恢复。
4. **不影响项目运行**：被移动的文件均为开发产物或历史文档，不影响后端 `uvicorn`、前端 `npm run dev` 或测试运行。

## 6. 后续处理建议

- **短期**：保留 `rubbish/` 目录 1-2 个迭代周期，便于回查。
- **中期**：确认无回滚需求后，可将 `rubbish/logs/` 下的 27 个日志文件直接删除（已无价值）。
- **长期**：项目正式提交复赛后，可整体删除 `rubbish/` 目录（保留本 README 至 docs/project-audit/ 作为清理记录）。
- **Git 策略**：`rubbish/` 目录已纳入版本控制（仅 README.md 与 git mv 的文件），未来若再有清理需求，请按本 README 格式追加记录。

# 任务报告：微信小程序全量对齐 Web/后端契约重构

## 1. 任务概述

按现行 Web 与后端契约重构微信小程序，修复学校坐标和学校切换运行时错误，并删除附近/GPS/距离能力。重构范围覆盖请求层、学校租户、认证、帖子、地点、互动、通知、订阅、专题及发布编辑。

## 2. 已完成内容

- 新增小程序共享类型和 `services/normalize.ts`，统一学校、帖子、图片、评论、通知、订阅、地点和摘要字段。
- 学校接口切换为 `/schools`、`/schools/current`、`/me/memberships`、`/schools/{code}/join`；请求层支持临时租户头和切校后旧缓存清理。
- 地图中心改用 `center_lat=31.483652`、`center_lng=120.271160`、`map_zoom=16`；地图顶部学校信息只读，地点标记来自 `/locations`。
- 微信注册改为 exchange → bind/register，注册选校只传 `school_id`，游客入口补齐。
- 帖子发布/编辑、图片上传、详情点赞评论、嵌套回复、状态和有效期改用现行字段；删除 `/posts/{id}/interactions`。
- 地点详情增加静态地点选择、名称/描述/楼栋/楼层搜索、摘要来源卡片和冲突/证据不足提示；删除 `chooseLocation` 权限配置。
- 通知全部已读改为 `PUT /notifications/read-all`，订阅改用 `target_type`，专题字段统一。
- 更新小程序 AI skill API 和契约说明，新增[契约矩阵与执行记录](../docs/小程序契约矩阵与重构执行记录.md)。
- 修复后端帖子列表游客路径的 `current_user` 未定义错误，并修复 Web 帖子回复的可空用户 ID类型错误。

## 3. 未完成内容

- 完整后端 `pytest backend/tests/ -v` 在 604 秒工具窗口内仍未结束并被超时终止，未得到全量汇总；针对本次契约影响模块的 79 项测试已全部通过（1 条既有 Pydantic serializer warning）。
- 微信自动化连接已恢复并完成邮箱登录 → “我的” → 选择浙江大学 → 地图/地点列表校验：本地 `school_code=zju`，地图数据为 `30.30485, 120.0817`，学校名与地点标记已更新；仍未完成微信注册、发布、详情互动、通知、订阅和地点摘要审核等完整 E2E。
- 管理端摘要审核队列属于 Web/后端既有能力，本次只接入小程序已批准摘要展示，没有新增管理端页面。

## 4. 实现思路

以 service 层归一化作为唯一边界，页面只消费规范模型；以 `X-School-Code` 和 `campusStore` 保证租户一致性；切校成功以目标学校详情请求完成为准；地图和发布地点均使用学校静态地点数据，不访问设备位置。

## 5. 修改文件

- `miniprogram/types/index.ts`、`miniprogram/services/normalize.ts`、`services/request.ts`、`services/schools.ts`、`services/posts.ts`、`services/interactions.ts`、`services/locations.ts`、`services/notifications.ts`、`services/subscriptions.ts`、`services/upload.ts`。
- 地图、首页、搜索、帖子详情、发布、编辑、个人中心、地点、通知、订阅、专题、登录、绑定和学校选择页面及模板。
- `miniprogram/app.json`、`miniprogram/skills/moment-campus/`、`docs/小程序契约矩阵与重构执行记录.md`、`TODO.md`。
- `backend/app/api/posts.py`、`frontend/src/pages/PostDetailPage.tsx`。

## 6. 影响范围

影响小程序所有用户端读取和写入链路，尤其是学校切换、地图地点、帖子发布编辑、互动和通知订阅。普通用户仍为一对一学校绑定；跨校管理继续留在 Web 管理端。历史任务报告未改写。

## 7. 测试与验证

- `miniprogram`: `npm run typecheck` 通过；`npm run test:format` 通过。
- 微信开发者工具：`check_wechatide_status` 已登录且版本匹配；`simulator_refresh` 通过；关键 9 个 WXML 文件 `compile_wxml` 通过；console grep 未发现 error/warn/fail；地图截图显示江南大学校区中心，未出现定位授权。
- Web：`frontend/npm run build` 通过。
- 后端：`test_schools_api.py`、`test_posts.py`、`test_interactions.py`、`test_notifications.py`、`test_subscriptions.py`、`test_location_summary_unit.py` 共 79 项通过；全量命令运行 604 秒后因超过执行窗口中止，未将其误报为完成。
- 自动化：`check_wechatide_status` 登录态与版本匹配；邮箱登录后 `isLoggedIn=true`，学校切换事务完成后 `wx.getStorageSync('school_code')=zju`，地图页读取到 `latitude=30.30485`、`longitude=120.0817`、`schoolName=浙江大学`，地点列表加载到浙大静态地点；未出现定位授权弹窗。完整写操作 E2E 仍待继续。

## 8. 后续建议

1. 在稳定的微信自动化登录态下跑完切校和写操作 E2E，并核对每个请求的 `X-School-Code`。
2. 将后端全量 pytest 放到 CI 或延长执行窗口，保留当前独立 `TEST_DATABASE_URL`。
3. 后续首页地点卡片和地图摘要预览只消费管理员已批准版本，不增加访问时生成逻辑。

# 任务报告：微信小程序全量对齐 Web/后端契约重构

## 1. 任务概述

按现行 Web 与后端契约重构微信小程序，修复学校坐标和学校切换运行时错误，并删除附近/GPS/距离能力。重构范围覆盖请求层、学校租户、认证、帖子、地点、互动、通知、分类/地点订阅及发布编辑；专题订阅入口按既有产品决策保持删除。

## 2. 已完成内容

- 新增小程序共享类型和 `services/normalize.ts`，统一学校、帖子、图片、评论、通知、订阅、地点和摘要字段。
- 学校接口切换为 `/schools`、`/schools/current`、`/me/memberships`、`/schools/{code}/join`；请求层支持临时租户头和切校后旧缓存清理。
- 地图中心改用 `center_lat=31.483652`、`center_lng=120.271160`、`map_zoom=16`；地图顶部学校信息只读，地点标记来自 `/locations`。
- 微信注册改为 exchange → bind/register，注册选校只传 `school_id`，游客入口补齐。
- 帖子发布/编辑、图片上传、详情点赞评论、嵌套回复、状态和有效期改用现行字段；删除 `/posts/{id}/interactions`。
- 地点详情增加静态地点选择、名称/描述/楼栋/楼层搜索、摘要来源卡片和冲突/证据不足提示；删除 `chooseLocation` 权限配置。
- 通知全部已读改为 `PUT /notifications/read-all`，订阅改用 `target_type`；专题订阅入口没有恢复，保持既有“专题与收藏入口已删除”口径。
- 修复邮箱切换账号时请求层继续复用旧 access token 的问题；`authStore` 登录/登出与请求层内存凭据现在原子同步。
- 修复小程序 JSCore 没有 `URLSearchParams` 导致通知、帖子、搜索、地点评价、推荐和订阅列表静默失败的问题，统一使用 `utils/query.ts` 编码查询参数。
- 通知页和订阅页增加登录生命周期竞态兜底，登录后首次进入仍会补加载列表；地点详情增加地点订阅入口。
- 更新小程序 AI skill API 和契约说明，新增[契约矩阵与执行记录](../docs/小程序契约矩阵与重构执行记录.md)。
- 修复后端帖子列表游客路径的 `current_user` 未定义错误，并修复 Web 帖子回复的可空用户 ID类型错误。

## 3. 未完成内容

- 完整后端 `pytest backend/tests/ -v` 在 604 秒工具窗口内仍未结束并被超时终止，未得到全量汇总；针对本次契约影响模块的 79 项测试已全部通过（1 条既有 Pydantic serializer warning）。
- 微信登录态 E2E 已补跑发布、互动、通知和订阅核心链路：发布帖子 1517、双账号点赞/评论/协同验证/举报、通知列表与全部已读、分类订阅和地点订阅请求均取得预期响应。账号切换时旧点赞状态不再泄漏。
- 远端体验环境的 `GET /locations/{id}` 与 `/reviews` 当前返回 404，导致地点详情弹层无法完成展示级 E2E；地点订阅请求通过页面 handler 重试后返回 201。该远端部署缺口未伪装为已完成。
- 专题订阅没有纳入本轮验证，也没有恢复已删除的专题页面入口；本轮产生的专题测试数据和订阅已清理。
- 管理端摘要审核队列属于 Web/后端既有能力，本次只接入小程序已批准摘要展示，没有新增管理端页面。

## 4. 实现思路

以 service 层归一化作为唯一边界，页面只消费规范模型；以 `X-School-Code` 和 `campusStore` 保证租户一致性；切校成功以目标学校详情请求完成为准；地图和发布地点均使用学校静态地点数据，不访问设备位置。

## 5. 修改文件

- `miniprogram/types/index.ts`、`miniprogram/services/normalize.ts`、`services/request.ts`、`services/schools.ts`、`services/posts.ts`、`services/interactions.ts`、`services/locations.ts`、`services/notifications.ts`、`services/subscriptions.ts`、`services/upload.ts`、`utils/query.ts`。
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
- 自动化：`check_wechatide_status` 登录态与版本匹配；邮箱登录后 `isLoggedIn=true`，学校切换事务完成后 `wx.getStorageSync('school_code')=zju`，地图页读取到 `latitude=30.30485`、`longitude=120.0817`、`schoolName=浙江大学`，地点列表加载到浙大静态地点；未出现定位授权弹窗。
- 发布与互动：小程序发布页创建帖子 1517（`POST /posts` 201），作者点赞/评论成功，作者投票收到预期 403；切换第二账号后点赞、评论、证实和举报分别返回 200/201/200/200，所有请求携带 `X-School-Code: zju`。
- 通知：作者通知列表返回 3 条未读互动/审核通知，点击“全部已读”调用 `PUT /notifications/read-all` 返回 200，页面未读数变为 0。
- 订阅：订阅管理页分类“分享吐槽”通过 `POST /subscriptions` 返回 201；地点订阅 handler 对“东区校门”通过同一接口返回 201。专题订阅未执行（入口已删除）。
- 已执行 `frontend/npm run build`、小程序 `npm run typecheck`、`npm run test:format` 与 3 个关键 WXML 编译检查，均通过。

## 8. 后续建议

1. 先将体验环境部署包含 `/locations/{id}`、地点评价和摘要路由的后端版本，再补地点详情展示级 E2E。
2. 将后端全量 pytest 放到 CI 或延长执行窗口，保留当前独立 `TEST_DATABASE_URL`。
3. 后续首页地点卡片和地图摘要预览只消费管理员已批准版本，不增加访问时生成逻辑；专题订阅保持删除。

# 任务报告：小程序 TabBar 切换闪烁与页面重复加载修复

## 1. 任务概述

排查并修复微信小程序真机上切换底部导航时，新旧高亮来回闪烁、部分页面首次进入或返回时出现空白和重复加载的问题。

## 2. 已完成内容

- 修复跨 Tab 页面独立自定义 TabBar 实例之间的高亮状态竞争。
- 移除会延长高亮重叠时间的背景动画、点击态滞留和模糊合成层。
- 阻止地图页首次进入时重复请求地点数据，并避免同校详情补全时清空已有标记。
- 为个人页增加 60 秒数据复用窗口，后台刷新时保留已有帖子和浏览历史。
- 在微信开发者工具中完成连续切换、请求次数、页面数据、样式编译和错误日志定向验证。

## 3. 未完成内容

暂无。本次未执行与问题无关的完整全链路测试，符合用户要求的定向测试范围。

## 4. 实现思路

自定义 TabBar 并非全局唯一组件，每个 Tab 页都持有一个可缓存实例。旧实现点击后先把源页面实例改成目标高亮，路由切换后目标页面缓存实例短暂显示自己的旧高亮，随后 `onShow` 再改正，因此形成肉眼可见的“新 → 旧 → 新”。修复后，切换前只记录目标路由，源页面保持原状态，目标页可见时由自身生命周期一次性写入正确高亮。

页面加载方面，地图页的校园状态订阅与 `onShow` 同时触发地点请求，而且学校详情补全会再次清空 marker。现在通过学校代码和请求版本锁去重；个人页则采用短时缓存并进行不清屏刷新，避免每次返回都先展示空列表。

## 5. 修改文件

- `miniprogram/utils/tab-navigation.ts`
- `miniprogram/custom-tab-bar/index.ts`
- `miniprogram/custom-tab-bar/index.wxml`
- `miniprogram/custom-tab-bar/index.wxss`
- `miniprogram/pages/map/map.ts`
- `miniprogram/pages/profile/profile.ts`
- `TODO.md`
- `CHANGELOG.md`
- `AIwork/小程序TabBar切换闪烁与页面重复加载修复任务报告.md`

## 6. 影响范围

影响小程序首页、地图、搜索、发布、个人中心五个主 Tab 的切换显示，以及地图地点初始化和个人中心返回时的数据刷新策略。不改动后端接口、业务权限和用户数据。

## 7. 测试与验证

- `npm run typecheck`：通过。
- `npm run test:format`：通过。
- `git diff --check`：通过。
- 微信开发者工具 `compile_wxml custom-tab-bar/index.wxml`：通过。
- 微信开发者工具 `compile_wxss custom-tab-bar/index.wxss`：通过。
- 微信开发者工具刷新后连续执行 6 次跨 Tab 切换：每次源页面 `selected` 在路由开始后仍保持原索引，目标页面首次读取即为目标索引。
- 地图首次进入：15 个 marker 正常加载；网络日志中 `/api/v1/locations` 为 1 次请求和 1 次成功响应，修复前同一流程为连续 2 次请求。
- 个人页缓存返回：个人页 → 首页 → 个人页后帖子仍为 8 条、`loadingPosts=false`，`/api/v1/users/me*` 新增请求数为 0。
- 模拟器 console 检索 `error|typeerror|fail|参数错误`：无匹配。
- 模拟器截图确认个人页内容和“我的”高亮完整显示，无空白首帧。

## 8. 后续建议

合入体验版后可在不同 Android/iOS 真机上各做一轮快速连续点击观察；若后续增加新的主 Tab，应继续遵循“目标页实例自行同步、源页不提前变更”的规则。

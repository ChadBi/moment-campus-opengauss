# 此刻校园 Skill

## 能力域定位

此刻校园是一个面向高校学生的实时生活分享与发现平台。本 Skill 提供浏览、搜索、发布、互动、话题、地图等核心能力，帮助用户在小程序 AI 对话中完成校园生活相关的信息获取与操作。

## 触发场景

用户可能的触发语：
- "看看此刻校园有什么新鲜事"
- "帮我找一下关于食堂的此刻"
- "发布一条失物招领"
- "看看这篇帖子详情"
- "帮我给这条此刻点个赞"
- "搜索一下'社团招新'"
- "看看热门话题"
- "查看校园地图上的地点和动态"
- "我的帖子列表"

## 不适用范围

- 需要支付的场景
- 需要扫码/相机的场景
- 外部链接跳转
- 文件下载

## 前置条件

- 用户需已登录此刻校园账号
- 需要有效的 access_token
- 需要网络连接

## 使用顺序

1. 浏览场景：listPosts → getPostDetail → likePost/createComment/validatePost
2. 搜索场景：searchPosts/aiSearch → getPostDetail
3. 发布场景：listCategories → createPost
4. 话题场景：listTopics → getTopicDetail → getPostDetail
5. 地图场景：getMapMarkers → getPostDetail
6. 通知场景：getNotifications
7. 个人场景：getMyPosts

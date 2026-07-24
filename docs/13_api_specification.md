# API 接口规范

> 此刻校园 · Moment Campus  
> 版本：1.0  
> 最后更新：2026-06-18

## 1. 文档概述

### 1.1 文档目的

本文档定义"此刻校园"平台的 API 接口规范，包括统一响应格式、各模块接口定义、业务错误码、排序和分页规范，为前后端开发提供统一的接口契约。

### 1.2 基础约定

- **基础路径**：`/api/v1`
- **协议**：HTTPS
- **数据格式**：JSON
- **字符编码**：UTF-8
- **认证方式**：Bearer Token（JWT）
- **时间格式**：ISO 8601（`2026-06-18T10:30:00+08:00`）

---

## 2. 统一响应格式

### 2.1 成功响应

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

### 2.2 失败响应

```json
{
  "code": 10001,
  "message": "用户名已存在",
  "data": null
}
```

### 2.3 分页响应

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [],
    "page": 1,
    "page_size": 20,
    "total": 100,
    "total_pages": 5
  }
}
```

### 2.4 响应字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| code | number | 业务状态码，0 表示成功，非 0 表示失败 |
| message | string | 响应消息 |
| data | object/null | 响应数据 |
| items | array | 分页数据列表 |
| page | number | 当前页码 |
| page_size | number | 每页数量 |
| total | number | 总记录数 |
| total_pages | number | 总页数 |

---

## 3. 业务错误码

### 3.1 错误码分配规则

| 错误码范围 | 模块 |
|------------|------|
| 10000-10999 | 认证相关 |
| 11000-11999 | 用户相关 |
| 12000-12999 | 信息相关 |
| 13000-13999 | 评论相关 |
| 14000-14999 | 互动相关 |
| 15000-15999 | 管理相关 |

### 3.2 认证模块错误码（10000-10999）

| 错误码 | 说明 |
|--------|------|
| 10001 | 用户名已存在 |
| 10002 | 邮箱已存在 |
| 10003 | 用户名或密码错误 |
| 10004 | 账号已被禁用 |
| 10005 | Token 无效 |
| 10006 | Token 已过期 |
| 10007 | 刷新 Token 无效 |
| 10008 | 密码强度不足 |
| 10009 | 旧密码错误 |
| 10010 | 登录失败次数过多，账号已锁定 |

### 3.3 用户模块错误码（11000-11999）

| 错误码 | 说明 |
|--------|------|
| 11001 | 用户不存在 |
| 11002 | 昵称已存在 |
| 11003 | 头像格式不支持 |
| 11004 | 头像大小超限 |
| 11005 | 未选择学校 |

### 3.4 信息模块错误码（12000-12999）

| 错误码 | 说明 |
|--------|------|
| 12001 | 信息不存在 |
| 12002 | 无权操作该信息 |
| 12003 | 信息已删除 |
| 12004 | 信息审核中 |
| 12005 | 信息已被拒绝 |
| 12006 | 标题长度不符合要求 |
| 12007 | 描述长度不符合要求 |
| 12008 | 分类不存在 |
| 12009 | 地点不存在 |
| 12010 | 图片数量超限 |
| 12011 | 标签数量超限 |

### 3.5 评论模块错误码（13000-13999）

| 错误码 | 说明 |
|--------|------|
| 13001 | 评论不存在 |
| 13002 | 无权删除该评论 |
| 13003 | 评论内容为空 |
| 13004 | 评论长度超限 |
| 13005 | 评论层级超限 |

### 3.6 互动模块错误码（14000-14999）

| 错误码 | 说明 |
|--------|------|
| 14001 | 已点赞 |
| 14002 | 未点赞 |
| 14003 | 已收藏 |
| 14004 | 未收藏 |
| 14005 | 已举报 |
| 14006 | 举报类型无效 |

### 3.7 管理模块错误码（15000-15999）

| 错误码 | 说明 |
|--------|------|
| 15001 | 无管理权限 |
| 15002 | 审核状态无效 |
| 15003 | 分类已存在 |
| 15004 | 标签已存在 |

---

## 4. 排序和分页规范

### 4.1 分页参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| page | number | 1 | 页码，从 1 开始 |
| page_size | number | 20 | 每页数量，可选值：10/20/50 |

### 4.2 排序参数

| 参数 | 说明 |
|------|------|
| sort | 排序字段 |
| order | 排序方向：asc/desc |

### 4.3 默认排序

| 模块 | 默认排序 |
|------|----------|
| 信息列表 | 综合排序（有效性×0.3 + 时间×0.25 + 距离×0.2 + 互动×0.15 + 质量×0.1） |
| 评论列表 | 时间倒序 |
| 通知列表 | 时间倒序 |
| 收藏列表 | 收藏时间倒序 |
| 浏览历史 | 浏览时间倒序 |

---

## 5. 认证模块

### 5.1 注册

**接口说明**：用户注册新账号

| 项目 | 说明 |
|------|------|
| 请求方法 | POST |
| 请求路径 | /auth/register |
| 需要登录 | 否 |

**请求体**：

```json
{
  "username": "string",
  "email": "string",
  "password": "string",
  "nickname": "string"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| username | string | 是 | 用户名，3-20字符，字母开头 |
| email | string | 是 | 邮箱地址 |
| password | string | 是 | 密码，8位以上，含字母和数字 |
| nickname | string | 是 | 昵称，2-20字符 |

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "user_id": "uuid",
    "username": "string",
    "email": "string",
    "nickname": "string",
    "access_token": "string",
    "refresh_token": "string",
    "expires_in": 7200
  }
}
```

**失败响应**：

| 错误码 | 说明 |
|--------|------|
| 10001 | 用户名已存在 |
| 10002 | 邮箱已存在 |
| 10008 | 密码强度不足 |

---

### 5.2 登录

**接口说明**：用户登录

| 项目 | 说明 |
|------|------|
| 请求方法 | POST |
| 请求路径 | /auth/login |
| 需要登录 | 否 |

**请求体**：

```json
{
  "account": "string",
  "password": "string"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| account | string | 是 | 用户名或邮箱 |
| password | string | 是 | 密码 |

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "user_id": "uuid",
    "username": "string",
    "nickname": "string",
    "avatar_url": "string",
    "access_token": "string",
    "refresh_token": "string",
    "expires_in": 7200
  }
}
```

**失败响应**：

| 错误码 | 说明 |
|--------|------|
| 10003 | 用户名或密码错误 |
| 10004 | 账号已被禁用 |
| 10010 | 登录失败次数过多，账号已锁定 |

---

### 5.3 登出

**接口说明**：用户登出

| 项目 | 说明 |
|------|------|
| 请求方法 | POST |
| 请求路径 | /auth/logout |
| 需要登录 | 是 |

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": null
}
```

---

### 5.4 刷新 Token

**接口说明**：刷新访问令牌

| 项目 | 说明 |
|------|------|
| 请求方法 | POST |
| 请求路径 | /auth/refresh |
| 需要登录 | 否 |

**请求体**：

```json
{
  "refresh_token": "string"
}
```

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "access_token": "string",
    "refresh_token": "string",
    "expires_in": 7200
  }
}
```

**失败响应**：

| 错误码 | 说明 |
|--------|------|
| 10007 | 刷新 Token 无效 |
| 10006 | Token 已过期 |

---

### 5.5 获取当前用户

**接口说明**：获取当前登录用户信息

| 项目 | 说明 |
|------|------|
| 请求方法 | GET |
| 请求路径 | /auth/me |
| 需要登录 | 是 |

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "user_id": "uuid",
    "username": "string",
    "email": "string",
    "nickname": "string",
    "avatar_url": "string",
    "bio": "string",
    "school_id": "uuid",
    "school_name": "string",
    "role": "user",
    "created_at": "datetime"
  }
}
```

**失败响应**：

| 错误码 | 说明 |
|--------|------|
| 10005 | Token 无效 |
| 10006 | Token 已过期 |

---

### 5.6 更新密码

**接口说明**：修改密码

| 项目 | 说明 |
|------|------|
| 请求方法 | PUT |
| 请求路径 | /auth/password |
| 需要登录 | 是 |

**请求体**：

```json
{
  "old_password": "string",
  "new_password": "string"
}
```

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": null
}
```

**失败响应**：

| 错误码 | 说明 |
|--------|------|
| 10009 | 旧密码错误 |
| 10008 | 密码强度不足 |

---

## 6. 用户模块

### 6.1 获取用户信息

**接口说明**：获取指定用户公开信息

| 项目 | 说明 |
|------|------|
| 请求方法 | GET |
| 请求路径 | /users/{user_id} |
| 需要登录 | 否 |

**路径参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| user_id | uuid | 用户ID |

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "user_id": "uuid",
    "nickname": "string",
    "avatar_url": "string",
    "bio": "string",
    "post_count": 0,
    "like_count": 0,
    "favorite_count": 0,
    "created_at": "datetime"
  }
}
```

**失败响应**：

| 错误码 | 说明 |
|--------|------|
| 11001 | 用户不存在 |

---

### 6.2 更新用户信息

**接口说明**：更新当前用户信息

| 项目 | 说明 |
|------|------|
| 请求方法 | PUT |
| 请求路径 | /users/me |
| 需要登录 | 是 |

**请求体**：

```json
{
  "nickname": "string",
  "bio": "string",
  "school_id": "uuid"
}
```

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "user_id": "uuid",
    "nickname": "string",
    "bio": "string",
    "school_id": "uuid",
    "updated_at": "datetime"
  }
}
```

**失败响应**：

| 错误码 | 说明 |
|--------|------|
| 11002 | 昵称已存在 |

---

### 6.3 上传头像

**接口说明**：上传用户头像

| 项目 | 说明 |
|------|------|
| 请求方法 | POST |
| 请求路径 | /users/me/avatar |
| 需要登录 | 是 |

**请求体**：multipart/form-data

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| file | file | 是 | 图片文件，支持 JPG/PNG，不超过 2MB |

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "avatar_url": "string"
  }
}
```

**失败响应**：

| 错误码 | 说明 |
|--------|------|
| 11003 | 头像格式不支持 |
| 11004 | 头像大小超限 |

---

### 6.4 获取用户主页

**接口说明**：获取用户主页信息（发布的公开信息）

| 项目 | 说明 |
|------|------|
| 请求方法 | GET |
| 请求路径 | /users/{user_id}/profile |
| 需要登录 | 否 |

**路径参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| user_id | uuid | 用户ID |

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | number | 否 | 页码，默认 1 |
| page_size | number | 否 | 每页数量，默认 20 |

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "user": {
      "user_id": "uuid",
      "nickname": "string",
      "avatar_url": "string",
      "bio": "string",
      "post_count": 0,
      "like_count": 0,
      "favorite_count": 0
    },
    "posts": {
      "items": [],
      "page": 1,
      "page_size": 20,
      "total": 0,
      "total_pages": 0
    }
  }
}
```

---

## 7. 学校模块

### 7.1 获取学校列表

**接口说明**：获取所有学校列表

| 项目 | 说明 |
|------|------|
| 请求方法 | GET |
| 请求路径 | /schools |
| 需要登录 | 否 |

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| keyword | string | 否 | 搜索关键词 |
| page | number | 否 | 页码 |
| page_size | number | 否 | 每页数量 |

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "school_id": "uuid",
        "name": "string",
        "short_name": "string",
        "logo_url": "string",
        "province": "string",
        "city": "string"
      }
    ],
    "page": 1,
    "page_size": 20,
    "total": 0,
    "total_pages": 0
  }
}
```

---

### 7.2 获取学校详情

**接口说明**：获取学校详细信息

| 项目 | 说明 |
|------|------|
| 请求方法 | GET |
| 请求路径 | /schools/{school_id} |
| 需要登录 | 否 |

**路径参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| school_id | uuid | 学校ID |

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "school_id": "uuid",
    "name": "string",
    "short_name": "string",
    "logo_url": "string",
    "province": "string",
    "city": "string",
    "address": "string",
    "description": "string",
    "post_count": 0,
    "user_count": 0
  }
}
```

---

## 8. 信息模块

### 8.1 创建信息

**接口说明**：发布新信息

| 项目 | 说明 |
|------|------|
| 请求方法 | POST |
| 请求路径 | /posts |
| 需要登录 | 是 |

**请求体**：

```json
{
  "title": "string",
  "description": "string",
  "category_id": "uuid",
  "location_id": "uuid",
  "tags": ["string"],
  "image_ids": ["uuid"],
  "validity_type": "permanent",
  "validity_days": 90,
  "validity_date": "date",
  "is_anonymous": false,
  "extra_data": {}
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| title | string | 是 | 标题，5-100字符 |
| description | string | 是 | 描述，10-5000字符 |
| category_id | uuid | 是 | 分类ID |
| location_id | uuid | 是 | 地点ID |
| tags | array | 否 | 标签列表，最多5个 |
| image_ids | array | 否 | 图片ID列表，最多9个 |
| validity_type | string | 否 | 有效期类型：permanent/short/custom |
| validity_days | number | 否 | 有效天数：7/30/90 |
| validity_date | date | 否 | 自定义有效日期 |
| is_anonymous | boolean | 否 | 是否匿名，默认 false |
| extra_data | object | 否 | 分类特有字段 |

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "post_id": "uuid",
    "status": "pending"
  }
}
```

**失败响应**：

| 错误码 | 说明 |
|--------|------|
| 12006 | 标题长度不符合要求 |
| 12007 | 描述长度不符合要求 |
| 12008 | 分类不存在 |
| 12009 | 地点不存在 |
| 12010 | 图片数量超限 |
| 12011 | 标签数量超限 |

---

### 8.2 获取信息列表

**接口说明**：获取信息列表（首页信息流）

| 项目 | 说明 |
|------|------|
| 请求方法 | GET |
| 请求路径 | /posts |
| 需要登录 | 否 |

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| school_id | uuid | 否 | 学校ID |
| category_id | uuid | 否 | 分类ID |
| tag | string | 否 | 标签筛选 |
| sort | string | 否 | 排序：comprehensive/latest/hottest |
| page | number | 否 | 页码 |
| page_size | number | 否 | 每页数量 |

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "post_id": "uuid",
        "title": "string",
        "description": "string",
        "category": {
          "category_id": "uuid",
          "name": "string",
          "icon": "string"
        },
        "location": {
          "location_id": "uuid",
          "name": "string"
        },
        "author": {
          "user_id": "uuid",
          "nickname": "string",
          "avatar_url": "string"
        },
        "cover_image": "string",
        "tags": ["string"],
        "validity_status": "valid",
        "like_count": 0,
        "comment_count": 0,
        "favorite_count": 0,
        "view_count": 0,
        "created_at": "datetime",
        "published_at": "datetime"
      }
    ],
    "page": 1,
    "page_size": 20,
    "total": 0,
    "total_pages": 0
  }
}
```

---

### 8.3 获取信息详情

**接口说明**：获取信息详细信息

| 项目 | 说明 |
|------|------|
| 请求方法 | GET |
| 请求路径 | /posts/{post_id} |
| 需要登录 | 否 |

**路径参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| post_id | uuid | 信息ID |

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "post_id": "uuid",
    "title": "string",
    "description": "string",
    "category": {
      "category_id": "uuid",
      "name": "string",
      "icon": "string"
    },
    "location": {
      "location_id": "uuid",
      "name": "string",
      "latitude": 0,
      "longitude": 0
    },
    "author": {
      "user_id": "uuid",
      "nickname": "string",
      "avatar_url": "string"
    },
    "images": [
      {
        "image_id": "uuid",
        "url": "string",
        "width": 0,
        "height": 0
      }
    ],
    "tags": ["string"],
    "validity_type": "permanent",
    "validity_status": "valid",
    "validity_date": "date",
    "valid_count": 0,
    "expired_count": 0,
    "like_count": 0,
    "comment_count": 0,
    "favorite_count": 0,
    "view_count": 0,
    "is_liked": false,
    "is_favorited": false,
    "extra_data": {},
    "created_at": "datetime",
    "updated_at": "datetime",
    "published_at": "datetime"
  }
}
```

**失败响应**：

| 错误码 | 说明 |
|--------|------|
| 12001 | 信息不存在 |
| 12003 | 信息已删除 |

---

### 8.4 更新信息

**接口说明**：更新自己的信息

| 项目 | 说明 |
|------|------|
| 请求方法 | PUT |
| 请求路径 | /posts/{post_id} |
| 需要登录 | 是 |

**路径参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| post_id | uuid | 信息ID |

**请求体**：同创建信息

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "post_id": "uuid",
    "updated_at": "datetime"
  }
}
```

**失败响应**：

| 错误码 | 说明 |
|--------|------|
| 12001 | 信息不存在 |
| 12002 | 无权操作该信息 |

---

### 8.5 删除信息

**接口说明**：删除自己的信息（软删除）

| 项目 | 说明 |
|------|------|
| 请求方法 | DELETE |
| 请求路径 | /posts/{post_id} |
| 需要登录 | 是 |

**路径参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| post_id | uuid | 信息ID |

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": null
}
```

**失败响应**：

| 错误码 | 说明 |
|--------|------|
| 12001 | 信息不存在 |
| 12002 | 无权操作该信息 |

---

### 8.6 获取我的信息

**接口说明**：获取当前用户发布的所有信息

| 项目 | 说明 |
|------|------|
| 请求方法 | GET |
| 请求路径 | /posts/mine |
| 需要登录 | 是 |

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| status | string | 否 | 状态筛选：published/pending/rejected/deleted |
| page | number | 否 | 页码 |
| page_size | number | 否 | 每页数量 |

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "post_id": "uuid",
        "title": "string",
        "status": "published",
        "validity_status": "valid",
        "like_count": 0,
        "comment_count": 0,
        "view_count": 0,
        "created_at": "datetime",
        "published_at": "datetime"
      }
    ],
    "page": 1,
    "page_size": 20,
    "total": 0,
    "total_pages": 0
  }
}
```

---

### 8.7 获取用户信息列表

**接口说明**：获取指定用户发布的公开信息

| 项目 | 说明 |
|------|------|
| 请求方法 | GET |
| 请求路径 | /users/{user_id}/posts |
| 需要登录 | 否 |

**路径参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| user_id | uuid | 用户ID |

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | number | 否 | 页码 |
| page_size | number | 否 | 每页数量 |

**成功响应**：同 8.2 获取信息列表

---

## 9. 地图模块

### 9.1 获取附近信息标记

**接口说明**：获取地图范围内的信息标记

| 项目 | 说明 |
|------|------|
| 请求方法 | GET |
| 请求路径 | /map/markers |
| 需要登录 | 否 |

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| school_id | uuid | 否 | 学校ID |
| latitude | number | 是 | 中心纬度 |
| longitude | number | 是 | 中心经度 |
| radius | number | 否 | 半径（米），默认 5000 |
| category_id | uuid | 否 | 分类筛选 |
| limit | number | 否 | 最大返回数量，默认 100 |

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "markers": [
      {
        "post_id": "uuid",
        "title": "string",
        "category_id": "uuid",
        "category_name": "string",
        "location": {
          "location_id": "uuid",
          "name": "string",
          "latitude": 0,
          "longitude": 0
        },
        "validity_status": "valid",
        "like_count": 0
      }
    ],
    "total": 0
  }
}
```

---

## 10. 搜索模块

### 10.1 搜索信息

**接口说明**：搜索信息

| 项目 | 说明 |
|------|------|
| 请求方法 | GET |
| 请求路径 | /search |
| 需要登录 | 否 |

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| keyword | string | 是 | 搜索关键词 |
| school_id | uuid | 否 | 学校ID |
| category_id | uuid | 否 | 分类筛选 |
| validity_status | string | 否 | 有效性筛选 |
| has_image | boolean | 否 | 是否有图片 |
| sort | string | 否 | 排序：comprehensive/distance/latest/hottest |
| latitude | number | 否 | 用户纬度（距离排序时需要） |
| longitude | number | 否 | 用户经度（距离排序时需要） |
| page | number | 否 | 页码 |
| page_size | number | 否 | 每页数量 |

**成功响应**：同 8.2 获取信息列表

---

## 11. 分类模块

### 11.1 获取分类列表

**接口说明**：获取所有分类

| 项目 | 说明 |
|------|------|
| 请求方法 | GET |
| 请求路径 | /categories |
| 需要登录 | 否 |

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": [
    {
      "category_id": "uuid",
      "name": "string",
      "icon": "string",
      "description": "string",
      "post_count": 0,
      "default_validity_days": 90
    }
  ]
}
```

---

### 11.2 获取分类详情

**接口说明**：获取分类详细信息

| 项目 | 说明 |
|------|------|
| 请求方法 | GET |
| 请求路径 | /categories/{category_id} |
| 需要登录 | 否 |

**路径参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| category_id | uuid | 分类ID |

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "category_id": "uuid",
    "name": "string",
    "icon": "string",
    "description": "string",
    "post_count": 0,
    "default_validity_days": 90,
    "preset_tags": ["string"],
    "extra_fields": []
  }
}
```

---

## 12. 标签模块

### 12.1 获取热门标签

**接口说明**：获取热门标签列表

| 项目 | 说明 |
|------|------|
| 请求方法 | GET |
| 请求路径 | /tags/hot |
| 需要登录 | 否 |

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| school_id | uuid | 否 | 学校ID |
| category_id | uuid | 否 | 分类ID |
| limit | number | 否 | 返回数量，默认 20 |

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": [
    {
      "tag": "string",
      "count": 0
    }
  ]
}
```

---

### 12.2 搜索标签

**接口说明**：搜索标签

| 项目 | 说明 |
|------|------|
| 请求方法 | GET |
| 请求路径 | /tags/search |
| 需要登录 | 否 |

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| keyword | string | 是 | 搜索关键词 |
| limit | number | 否 | 返回数量，默认 10 |

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": ["string"]
}
```

---

## 13. 图片模块

### 13.1 上传图片

**接口说明**：上传图片

| 项目 | 说明 |
|------|------|
| 请求方法 | POST |
| 请求路径 | /images/upload |
| 需要登录 | 是 |

**请求体**：multipart/form-data

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| file | file | 是 | 图片文件，支持 JPG/PNG/GIF，不超过 5MB |

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "image_id": "uuid",
    "url": "string",
    "width": 0,
    "height": 0,
    "size": 0
  }
}
```

---

### 13.2 删除图片

**接口说明**：删除图片

| 项目 | 说明 |
|------|------|
| 请求方法 | DELETE |
| 请求路径 | /images/{image_id} |
| 需要登录 | 是 |

**路径参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| image_id | uuid | 图片ID |

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": null
}
```

---

## 14. 评论模块

### 14.1 获取评论列表

**接口说明**：获取信息的评论列表

| 项目 | 说明 |
|------|------|
| 请求方法 | GET |
| 请求路径 | /posts/{post_id}/comments |
| 需要登录 | 否 |

**路径参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| post_id | uuid | 信息ID |

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| sort | string | 否 | 排序：latest/oldest/hottest |
| page | number | 否 | 页码 |
| page_size | number | 否 | 每页数量 |

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "comment_id": "uuid",
        "content": "string",
        "author": {
          "user_id": "uuid",
          "nickname": "string",
          "avatar_url": "string"
        },
        "reply_to": {
          "user_id": "uuid",
          "nickname": "string"
        },
        "like_count": 0,
        "reply_count": 0,
        "created_at": "datetime"
      }
    ],
    "page": 1,
    "page_size": 20,
    "total": 0,
    "total_pages": 0
  }
}
```

---

### 14.2 创建评论

**接口说明**：发表评论

| 项目 | 说明 |
|------|------|
| 请求方法 | POST |
| 请求路径 | /posts/{post_id}/comments |
| 需要登录 | 是 |

**路径参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| post_id | uuid | 信息ID |

**请求体**：

```json
{
  "content": "string",
  "reply_to_comment_id": "uuid"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| content | string | 是 | 评论内容，1-1000字符 |
| reply_to_comment_id | uuid | 否 | 回复的评论ID |

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "comment_id": "uuid",
    "created_at": "datetime"
  }
}
```

**失败响应**：

| 错误码 | 说明 |
|--------|------|
| 13003 | 评论内容为空 |
| 13004 | 评论长度超限 |
| 13005 | 评论层级超限 |

---

### 14.3 删除评论

**接口说明**：删除自己的评论

| 项目 | 说明 |
|------|------|
| 请求方法 | DELETE |
| 请求路径 | /comments/{comment_id} |
| 需要登录 | 是 |

**路径参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| comment_id | uuid | 评论ID |

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": null
}
```

**失败响应**：

| 错误码 | 说明 |
|--------|------|
| 13001 | 评论不存在 |
| 13002 | 无权删除该评论 |

---

### 14.4 获取回复列表

**接口说明**：获取评论的回复列表

| 项目 | 说明 |
|------|------|
| 请求方法 | GET |
| 请求路径 | /comments/{comment_id}/replies |
| 需要登录 | 否 |

**路径参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| comment_id | uuid | 评论ID |

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | number | 否 | 页码 |
| page_size | number | 否 | 每页数量 |

**成功响应**：同 14.1 获取评论列表

---

## 15. 点赞模块

### 15.1 点赞

**接口说明**：对信息点赞

| 项目 | 说明 |
|------|------|
| 请求方法 | POST |
| 请求路径 | /posts/{post_id}/like |
| 需要登录 | 是 |

**路径参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| post_id | uuid | 信息ID |

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "like_count": 0
  }
}
```

**失败响应**：

| 错误码 | 说明 |
|--------|------|
| 14001 | 已点赞 |

---

### 15.2 取消点赞

**接口说明**：取消对信息的点赞

| 项目 | 说明 |
|------|------|
| 请求方法 | DELETE |
| 请求路径 | /posts/{post_id}/like |
| 需要登录 | 是 |

**路径参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| post_id | uuid | 信息ID |

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "like_count": 0
  }
}
```

**失败响应**：

| 错误码 | 说明 |
|--------|------|
| 14002 | 未点赞 |

---

## 16. 收藏模块

### 16.1 收藏

**接口说明**：收藏信息

| 项目 | 说明 |
|------|------|
| 请求方法 | POST |
| 请求路径 | /posts/{post_id}/favorite |
| 需要登录 | 是 |

**路径参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| post_id | uuid | 信息ID |

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "favorite_count": 0
  }
}
```

**失败响应**：

| 错误码 | 说明 |
|--------|------|
| 14003 | 已收藏 |

---

### 16.2 取消收藏

**接口说明**：取消收藏

| 项目 | 说明 |
|------|------|
| 请求方法 | DELETE |
| 请求路径 | /posts/{post_id}/favorite |
| 需要登录 | 是 |

**路径参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| post_id | uuid | 信息ID |

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "favorite_count": 0
  }
}
```

**失败响应**：

| 错误码 | 说明 |
|--------|------|
| 14004 | 未收藏 |

---

### 16.3 获取收藏列表

**接口说明**：获取当前用户的收藏列表

| 项目 | 说明 |
|------|------|
| 请求方法 | GET |
| 请求路径 | /favorites |
| 需要登录 | 是 |

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | number | 否 | 页码 |
| page_size | number | 否 | 每页数量 |

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "favorite_id": "uuid",
        "post": {
          "post_id": "uuid",
          "title": "string",
          "cover_image": "string",
          "validity_status": "valid"
        },
        "favorited_at": "datetime"
      }
    ],
    "page": 1,
    "page_size": 20,
    "total": 0,
    "total_pages": 0
  }
}
```

---

## 17. 有效性验证模块

### 17.1 提交有效性确认

**接口说明**：确认信息是否仍然有效

| 项目 | 说明 |
|------|------|
| 请求方法 | POST |
| 请求路径 | /posts/{post_id}/validity |
| 需要登录 | 是 |

**路径参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| post_id | uuid | 信息ID |

**请求体**：

```json
{
  "status": "valid"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| status | string | 是 | 确认状态：valid/expired/uncertain |

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "valid_count": 0,
    "expired_count": 0,
    "validity_status": "valid"
  }
}
```

---

### 17.2 获取有效性统计

**接口说明**：获取信息的有效性统计

| 项目 | 说明 |
|------|------|
| 请求方法 | GET |
| 请求路径 | /posts/{post_id}/validity |
| 需要登录 | 否 |

**路径参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| post_id | uuid | 信息ID |

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "valid_count": 0,
    "expired_count": 0,
    "uncertain_count": 0,
    "validity_status": "valid",
    "records": [
      {
        "user_id": "uuid",
        "nickname": "string",
        "status": "valid",
        "created_at": "datetime"
      }
    ]
  }
}
```

---

## 18. 举报模块

### 18.1 提交举报

**接口说明**：举报违规内容

| 项目 | 说明 |
|------|------|
| 请求方法 | POST |
| 请求路径 | /reports |
| 需要登录 | 是 |

**请求体**：

```json
{
  "target_type": "post",
  "target_id": "uuid",
  "reason": "spam",
  "description": "string"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| target_type | string | 是 | 目标类型：post/comment |
| target_id | uuid | 是 | 目标ID |
| reason | string | 是 | 举报原因：spam/false_info/privacy/illegal/other |
| description | string | 否 | 详细描述，最多500字符 |

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "report_id": "uuid"
  }
}
```

**失败响应**：

| 错误码 | 说明 |
|--------|------|
| 14005 | 已举报 |
| 14006 | 举报类型无效 |

---

### 18.2 获取我的举报

**接口说明**：获取当前用户提交的举报列表

| 项目 | 说明 |
|------|------|
| 请求方法 | GET |
| 请求路径 | /reports/mine |
| 需要登录 | 是 |

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| status | string | 否 | 状态筛选：pending/processed/rejected |
| page | number | 否 | 页码 |
| page_size | number | 否 | 每页数量 |

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "report_id": "uuid",
        "target_type": "post",
        "target_id": "uuid",
        "target_title": "string",
        "reason": "string",
        "status": "pending",
        "created_at": "datetime",
        "processed_at": "datetime"
      }
    ],
    "page": 1,
    "page_size": 20,
    "total": 0,
    "total_pages": 0
  }
}
```

---

## 19. 通知模块

### 19.1 获取通知列表

**接口说明**：获取当前用户的通知列表

| 项目 | 说明 |
|------|------|
| 请求方法 | GET |
| 请求路径 | /notifications |
| 需要登录 | 是 |

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| type | string | 否 | 类型筛选：comment/like/system/audit |
| is_read | boolean | 否 | 是否已读 |
| page | number | 否 | 页码 |
| page_size | number | 否 | 每页数量 |

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "notification_id": "uuid",
        "type": "comment",
        "title": "string",
        "content": "string",
        "target_url": "string",
        "is_read": false,
        "created_at": "datetime"
      }
    ],
    "page": 1,
    "page_size": 20,
    "total": 0,
    "total_pages": 0
  }
}
```

---

### 19.2 标记已读

**接口说明**：标记通知为已读

| 项目 | 说明 |
|------|------|
| 请求方法 | PUT |
| 请求路径 | /notifications/read |
| 需要登录 | 是 |

**请求体**：

```json
{
  "notification_ids": ["uuid"]
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| notification_ids | array | 否 | 通知ID列表，为空则标记全部已读 |

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "read_count": 0
  }
}
```

---

### 19.3 获取未读数

**接口说明**：获取未读通知数量

| 项目 | 说明 |
|------|------|
| 请求方法 | GET |
| 请求路径 | /notifications/unread-count |
| 需要登录 | 是 |

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "total": 0,
    "comment": 0,
    "like": 0,
    "system": 0,
    "audit": 0
  }
}
```

---

## 20. 专题模块

### 20.1 获取专题列表

**接口说明**：获取专题列表

| 项目 | 说明 |
|------|------|
| 请求方法 | GET |
| 请求路径 | /topics |
| 需要登录 | 否 |

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| school_id | uuid | 否 | 学校ID |
| sort | string | 否 | 排序：latest/hottest |
| page | number | 否 | 页码 |
| page_size | number | 否 | 每页数量 |

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "topic_id": "uuid",
        "title": "string",
        "description": "string",
        "cover_url": "string",
        "post_count": 0,
        "view_count": 0,
        "author": {
          "user_id": "uuid",
          "nickname": "string"
        },
        "created_at": "datetime"
      }
    ],
    "page": 1,
    "page_size": 20,
    "total": 0,
    "total_pages": 0
  }
}
```

---

### 20.2 获取专题详情

**接口说明**：获取专题详细信息

| 项目 | 说明 |
|------|------|
| 请求方法 | GET |
| 请求路径 | /topics/{topic_id} |
| 需要登录 | 否 |

**路径参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| topic_id | uuid | 专题ID |

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | number | 否 | 页码 |
| page_size | number | 否 | 每页数量 |

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "topic_id": "uuid",
    "title": "string",
    "description": "string",
    "cover_url": "string",
    "author": {
      "user_id": "uuid",
      "nickname": "string",
      "avatar_url": "string"
    },
    "post_count": 0,
    "view_count": 0,
    "created_at": "datetime",
    "posts": {
      "items": [],
      "page": 1,
      "page_size": 20,
      "total": 0,
      "total_pages": 0
    }
  }
}
```

---

### 20.3 创建专题

**接口说明**：创建专题

| 项目 | 说明 |
|------|------|
| 请求方法 | POST |
| 请求路径 | /topics |
| 需要登录 | 是 |

**请求体**：

```json
{
  "title": "string",
  "description": "string",
  "cover_image_id": "uuid",
  "post_ids": ["uuid"]
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| title | string | 是 | 标题，5-50字符 |
| description | string | 否 | 描述，最多200字符 |
| cover_image_id | uuid | 否 | 封面图片ID |
| post_ids | array | 否 | 初始信息ID列表 |

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "topic_id": "uuid"
  }
}
```

---

### 20.4 更新专题

**接口说明**：更新专题

| 项目 | 说明 |
|------|------|
| 请求方法 | PUT |
| 请求路径 | /topics/{topic_id} |
| 需要登录 | 是 |

**路径参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| topic_id | uuid | 专题ID |

**请求体**：

```json
{
  "title": "string",
  "description": "string",
  "cover_image_id": "uuid",
  "post_ids": ["uuid"]
}
```

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "topic_id": "uuid",
    "updated_at": "datetime"
  }
}
```

---

## 21. 草稿模块

### 21.1 创建草稿

**接口说明**：创建草稿

| 项目 | 说明 |
|------|------|
| 请求方法 | POST |
| 请求路径 | /drafts |
| 需要登录 | 是 |

**请求体**：同创建信息

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "draft_id": "uuid"
  }
}
```

---

### 21.2 获取草稿列表

**接口说明**：获取当前用户的草稿列表

| 项目 | 说明 |
|------|------|
| 请求方法 | GET |
| 请求路径 | /drafts |
| 需要登录 | 是 |

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | number | 否 | 页码 |
| page_size | number | 否 | 每页数量 |

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "draft_id": "uuid",
        "title": "string",
        "category_name": "string",
        "updated_at": "datetime"
      }
    ],
    "page": 1,
    "page_size": 20,
    "total": 0,
    "total_pages": 0
  }
}
```

---

### 21.3 更新草稿

**接口说明**：更新草稿

| 项目 | 说明 |
|------|------|
| 请求方法 | PUT |
| 请求路径 | /drafts/{draft_id} |
| 需要登录 | 是 |

**路径参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| draft_id | uuid | 草稿ID |

**请求体**：同创建信息

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "draft_id": "uuid",
    "updated_at": "datetime"
  }
}
```

---

### 21.4 删除草稿

**接口说明**：删除草稿

| 项目 | 说明 |
|------|------|
| 请求方法 | DELETE |
| 请求路径 | /drafts/{draft_id} |
| 需要登录 | 是 |

**路径参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| draft_id | uuid | 草稿ID |

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": null
}
```

---

## 22. 浏览历史模块

### 22.1 获取浏览历史

**接口说明**：获取当前用户的浏览历史

| 项目 | 说明 |
|------|------|
| 请求方法 | GET |
| 请求路径 | /history |
| 需要登录 | 是 |

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | number | 否 | 页码 |
| page_size | number | 否 | 每页数量 |

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "history_id": "uuid",
        "post": {
          "post_id": "uuid",
          "title": "string",
          "cover_image": "string",
          "category_name": "string"
        },
        "viewed_at": "datetime"
      }
    ],
    "page": 1,
    "page_size": 20,
    "total": 0,
    "total_pages": 0
  }
}
```

---

### 22.2 清除浏览历史

**接口说明**：清除浏览历史

| 项目 | 说明 |
|------|------|
| 请求方法 | DELETE |
| 请求路径 | /history |
| 需要登录 | 是 |

**请求体**：

```json
{
  "history_ids": ["uuid"]
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| history_ids | array | 否 | 历史记录ID列表，为空则清除全部 |

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "deleted_count": 0
  }
}
```

---

## 23. 管理后台模块

### 23.1 获取统计数据

**接口说明**：获取后台统计数据

| 项目 | 说明 |
|------|------|
| 请求方法 | GET |
| 请求路径 | /admin/statistics |
| 需要登录 | 是 |
| 权限要求 | 管理员 |

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "total_users": 0,
    "total_posts": 0,
    "pending_posts": 0,
    "today_new_posts": 0,
    "total_reports": 0,
    "pending_reports": 0
  }
}
```

**失败响应**：

| 错误码 | 说明 |
|--------|------|
| 15001 | 无管理权限 |

---

### 23.2 审核信息

**接口说明**：审核通过信息

| 项目 | 说明 |
|------|------|
| 请求方法 | POST |
| 请求路径 | /admin/posts/{post_id}/approve |
| 需要登录 | 是 |
| 权限要求 | 管理员 |

**路径参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| post_id | uuid | 信息ID |

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": null
}
```

---

### 23.3 拒绝信息

**接口说明**：拒绝信息

| 项目 | 说明 |
|------|------|
| 请求方法 | POST |
| 请求路径 | /admin/posts/{post_id}/reject |
| 需要登录 | 是 |
| 权限要求 | 管理员 |

**路径参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| post_id | uuid | 信息ID |

**请求体**：

```json
{
  "reason": "string"
}
```

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": null
}
```

---

### 23.4 隐藏信息

**接口说明**：隐藏信息

| 项目 | 说明 |
|------|------|
| 请求方法 | POST |
| 请求路径 | /admin/posts/{post_id}/hide |
| 需要登录 | 是 |
| 权限要求 | 管理员 |

**路径参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| post_id | uuid | 信息ID |

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": null
}
```

---

### 23.5 处理举报

**接口说明**：处理举报

| 项目 | 说明 |
|------|------|
| 请求方法 | POST |
| 请求路径 | /admin/reports/{report_id}/process |
| 需要登录 | 是 |
| 权限要求 | 管理员 |

**路径参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| report_id | uuid | 举报ID |

**请求体**：

```json
{
  "action": "accept",
  "remark": "string"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| action | string | 是 | 处理动作：accept/reject |
| remark | string | 否 | 处理备注 |

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": null
}
```

---

### 23.6 获取用户列表

**接口说明**：获取用户列表

| 项目 | 说明 |
|------|------|
| 请求方法 | GET |
| 请求路径 | /admin/users |
| 需要登录 | 是 |
| 权限要求 | 管理员 |

**查询参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| keyword | string | 否 | 搜索关键词 |
| status | string | 否 | 状态筛选：active/disabled |
| page | number | 否 | 页码 |
| page_size | number | 否 | 每页数量 |

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "user_id": "uuid",
        "username": "string",
        "nickname": "string",
        "email": "string",
        "status": "active",
        "post_count": 0,
        "created_at": "datetime"
      }
    ],
    "page": 1,
    "page_size": 20,
    "total": 0,
    "total_pages": 0
  }
}
```

---

### 23.7 禁用用户

**接口说明**：禁用/启用用户

| 项目 | 说明 |
|------|------|
| 请求方法 | POST |
| 请求路径 | /admin/users/{user_id}/status |
| 需要登录 | 是 |
| 权限要求 | 管理员 |

**路径参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| user_id | uuid | 用户ID |

**请求体**：

```json
{
  "status": "disabled",
  "reason": "string"
}
```

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": null
}
```

---

### 23.8 管理分类

**接口说明**：创建/更新/删除分类

| 项目 | 说明 |
|------|------|
| 请求方法 | POST/PUT/DELETE |
| 请求路径 | /admin/categories |
| 需要登录 | 是 |
| 权限要求 | 管理员 |

**创建请求体**：

```json
{
  "name": "string",
  "icon": "string",
  "description": "string",
  "default_validity_days": 90,
  "preset_tags": ["string"],
  "extra_fields": []
}
```

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "category_id": "uuid"
  }
}
```

---

### 23.9 管理标签

**接口说明**：管理系统标签

| 项目 | 说明 |
|------|------|
| 请求方法 | POST/PUT/DELETE |
| 请求路径 | /admin/tags |
| 需要登录 | 是 |
| 权限要求 | 管理员 |

**创建请求体**：

```json
{
  "tag": "string",
  "category_id": "uuid"
}
```

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "tag_id": "uuid"
  }
}
```

---

### 23.10 管理专题

**接口说明**：管理专题（置顶/推荐/删除）

| 项目 | 说明 |
|------|------|
| 请求方法 | POST |
| 请求路径 | /admin/topics/{topic_id}/action |
| 需要登录 | 是 |
| 权限要求 | 管理员 |

**路径参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| topic_id | uuid | 专题ID |

**请求体**：

```json
{
  "action": "pin",
  "value": true
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| action | string | 是 | 操作：pin/recommend/delete |
| value | boolean | 否 | 操作值 |

**成功响应**：

```json
{
  "code": 0,
  "message": "success",
  "data": null
}
```

---

## 24. 相关文档

- [项目总览](00_project_overview.md)
- [产品需求文档](01_product_requirements.md)
- [功能范围与优先级](03_feature_scope_and_priority.md)
- [数据库设计](12_database_design.md)
- [安全与隐私](14_security_and_privacy.md)

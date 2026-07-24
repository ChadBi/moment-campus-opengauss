# 测试与验收

> 此刻校园 · Moment Campus  
> 版本：1.0  
> 最后更新：2026-06-18

## 1. 测试策略

### 1.1 测试金字塔

采用经典的测试金字塔模型，确保测试覆盖全面且高效：

```
        ╱  E2E 测试  ╲         (5%)
       ╱  端到端场景  ╲        
      ╱────────────────╲       
     ╱   集成测试        ╲      (25%)
    ╱  API + 组件集成      ╲     
   ╱────────────────────────╲    
  ╱      单元测试             ╲   (70%)
 ╱  函数 + 组件 + 业务逻辑      ╲  
╱────────────────────────────────╲ 
```

**测试层级说明：**

| 测试层级 | 占比 | 说明 | 执行频率 |
|----------|------|------|----------|
| 单元测试 | 70% | 测试独立的函数、组件、业务逻辑 | 每次提交 |
| 集成测试 | 25% | 测试模块间交互、API接口、组件集成 | 每次提交 |
| E2E测试 | 5% | 测试完整用户流程、关键业务场景 | 每日构建 |

### 1.2 测试工具

**前端测试工具栈：**

| 工具 | 用途 | 说明 |
|------|------|------|
| Vitest | 单元测试 | 快速、原生的 Vite 测试框架 |
| React Testing Library | 组件测试 | 测试 React 组件的用户行为 |
| Playwright | E2E测试 | 跨浏览器端到端测试 |
| MSW (Mock Service Worker) | API模拟 | 前端测试时模拟后端API |

**后端测试工具栈：**

| 工具 | 用途 | 说明 |
|------|------|------|
| pytest | 测试框架 | Python 测试框架 |
| pytest-asyncio | 异步测试 | 支持 FastAPI 异步接口测试 |
| httpx | API测试 | 异步 HTTP 客户端测试 |
| SQLAlchemy Test | 数据库测试 | 测试数据库操作 |
| Factory Boy | 测试数据 | 生成测试数据 |

### 1.3 测试覆盖率目标

**前端覆盖率目标：**

| 模块 | 行覆盖率 | 分支覆盖率 | 说明 |
|------|----------|------------|------|
| 核心组件 | ≥80% | ≥70% | 信息卡片、表单、导航等 |
| 业务逻辑 | ≥90% | ≥80% | hooks、工具函数、状态管理 |
| 页面组件 | ≥70% | ≥60% | 首页、详情页、发布页等 |
| 整体覆盖率 | ≥75% | ≥65% | 项目整体要求 |

**后端覆盖率目标：**

| 模块 | 行覆盖率 | 分支覆盖率 | 说明 |
|------|----------|------------|------|
| API接口 | ≥90% | ≥85% | 所有接口必须测试 |
| 业务逻辑 | ≥95% | ≥90% | 核心业务逻辑 |
| 数据模型 | ≥85% | ≥80% | 数据库操作 |
| 认证授权 | ≥95% | ≥90% | 安全相关 |
| 整体覆盖率 | ≥85% | ≥80% | 项目整体要求 |

---

## 2. 前端测试

### 2.1 组件测试

**测试范围：**

- 基础UI组件（Button、Input、Card、Modal等）
- 业务组件（信息卡片、评论列表、地图标记等）
- 表单组件（发布表单、登录表单、搜索表单等）

**测试要点：**

```typescript
// 示例：信息卡片组件测试
describe('PostCard', () => {
  it('应正确渲染标题和分类', () => {
    render(<PostCard post={mockPost} />);
    expect(screen.getByText(mockPost.title)).toBeInTheDocument();
    expect(screen.getByText(mockPost.category.name)).toBeInTheDocument();
  });

  it('点击卡片应跳转到详情页', async () => {
    const user = userEvent.setup();
    render(<PostCard post={mockPost} />);
    await user.click(screen.getByRole('link'));
    expect(mockNavigate).toHaveBeenCalledWith(`/post/${mockPost.id}`);
  });

  it('应显示有效性状态标识', () => {
    render(<PostCard post={{ ...mockPost, validityStatus: 'valid' }} />);
    expect(screen.getByTestId('validity-badge')).toHaveTextContent('有效');
  });

  it('无图片时不应渲染图片区域', () => {
    render(<PostCard post={{ ...mockPost, images: [] }} />);
    expect(screen.queryByTestId('post-image')).not.toBeInTheDocument();
  });
});
```

**组件测试检查项：**

- 正确渲染传入的props
- 用户交互事件（点击、输入、选择等）
- 条件渲染逻辑
- 样式和类名应用
- 错误边界处理
- 加载状态显示
- 空状态处理

### 2.2 页面测试

**测试范围：**

- 首页（推荐信息流、分类入口）
- 信息详情页（内容展示、互动操作）
- 发布页（表单填写、图片上传）
- 个人中心（用户信息、我的发布/收藏）
- 搜索结果页（搜索列表、筛选条件）

**测试要点：**

```typescript
// 示例：首页测试
describe('HomePage', () => {
  it('应加载并显示推荐信息流', async () => {
    render(<HomePage />);
    
    // 显示加载状态
    expect(screen.getByTestId('loading')).toBeInTheDocument();
    
    // 等待数据加载完成
    await waitFor(() => {
      expect(screen.queryByTestId('loading')).not.toBeInTheDocument();
    });
    
    // 显示信息列表
    const posts = screen.getAllByTestId('post-card');
    expect(posts.length).toBeGreaterThan(0);
  });

  it('下拉刷新应重新加载数据', async () => {
    const user = userEvent.setup();
    render(<HomePage />);
    
    await waitFor(() => {
      expect(screen.getAllByTestId('post-card').length).toBeGreaterThan(0);
    });
    
    // 模拟下拉刷新
    await user.pullDown(screen.getByTestId('refresh-container'));
    
    // 验证重新请求数据
    await waitFor(() => {
      expect(mockApi.getPosts).toHaveBeenCalledTimes(2);
    });
  });

  it('点击分类应跳转到分类详情页', async () => {
    const user = userEvent.setup();
    render(<HomePage />);
    
    await user.click(screen.getByText('校园美食'));
    expect(mockNavigate).toHaveBeenCalledWith('/category/food');
  });
});
```

**页面测试检查项：**

- 页面初始加载和数据获取
- 路由跳转和参数传递
- 页面状态管理（加载、错误、空状态）
- 页面间数据传递
- 浏览器历史记录处理
- 页面生命周期（挂载、卸载、更新）

### 2.3 交互测试

**测试范围：**

- 表单提交和验证
- 点赞、收藏、评论操作
- 图片上传和预览
- 地图交互（缩放、拖动、标记点击）
- 搜索和筛选操作
- 下拉刷新和无限滚动

**测试要点：**

```typescript
// 示例：发布表单交互测试
describe('PostForm', () => {
  it('应验证必填字段', async () => {
    const user = userEvent.setup();
    render(<PostForm />);
    
    // 直接提交空表单
    await user.click(screen.getByRole('button', { name: '发布' }));
    
    // 验证错误提示
    expect(screen.getByText('请选择分类')).toBeInTheDocument();
    expect(screen.getByText('标题不能为空')).toBeInTheDocument();
    expect(screen.getByText('描述不能为空')).toBeInTheDocument();
  });

  it('上传图片应显示预览', async () => {
    const user = userEvent.setup();
    render(<PostForm />);
    
    const file = new File(['dummy content'], 'example.png', { type: 'image/png' });
    const input = screen.getByTestId('image-upload');
    
    await user.upload(input, file);
    
    // 验证预览显示
    await waitFor(() => {
      expect(screen.getByAltText('预览图')).toBeInTheDocument();
    });
  });

  it('敏感信息检测应提示用户', async () => {
    const user = userEvent.setup();
    render(<PostForm />);
    
    // 输入包含手机号的内容
    await user.type(screen.getByLabelText('描述'), '联系电话：13812345678');
    
    // 验证提示显示
    await waitFor(() => {
      expect(screen.getByText('检测到敏感信息：手机号')).toBeInTheDocument();
    });
  });
});

// 示例：点赞交互测试
describe('LikeButton', () => {
  it('点赞应更新计数并改变状态', async () => {
    const user = userEvent.setup();
    render(<LikeButton postId="1" initialCount={10} />);
    
    expect(screen.getByText('10')).toBeInTheDocument();
    expect(screen.getByRole('button')).not.toHaveClass('liked');
    
    await user.click(screen.getByRole('button'));
    
    await waitFor(() => {
      expect(screen.getByText('11')).toBeInTheDocument();
      expect(screen.getByRole('button')).toHaveClass('liked');
    });
  });

  it('重复点赞应取消点赞', async () => {
    const user = userEvent.setup();
    render(<LikeButton postId="1" initialCount={10} isLiked={true} />);
    
    await user.click(screen.getByRole('button'));
    
    await waitFor(() => {
      expect(screen.getByText('9')).toBeInTheDocument();
      expect(screen.getByRole('button')).not.toHaveClass('liked');
    });
  });
});
```

**交互测试检查项：**

- 用户输入验证和反馈
- 异步操作的状态变化
- 乐观更新和错误回滚
- 防抖和节流处理
- 键盘和触摸事件
- 焦点管理和可访问性

### 2.4 响应式测试

**测试断点：**

| 设备类型 | 宽度范围 | 测试重点 |
|----------|----------|----------|
| 移动端 | 320px - 767px | 触摸操作、底部导航、单列布局 |
| 平板端 | 768px - 1023px | 双列布局、侧边导航 |
| 桌面端 | 1024px - 1920px | 多列布局、完整导航 |

**测试要点：**

```typescript
// 示例：响应式布局测试
describe('ResponsiveLayout', () => {
  it('移动端应显示底部导航', () => {
    // 设置移动端视口
    window.resizeTo(375, 667);
    
    render(<Layout />);
    
    expect(screen.getByTestId('bottom-nav')).toBeInTheDocument();
    expect(screen.queryByTestId('sidebar')).not.toBeInTheDocument();
  });

  it('桌面端应显示侧边导航', () => {
    // 设置桌面端视口
    window.resizeTo(1440, 900);
    
    render(<Layout />);
    
    expect(screen.getByTestId('sidebar')).toBeInTheDocument();
    expect(screen.queryByTestId('bottom-nav')).not.toBeInTheDocument();
  });

  it('信息流在移动端应为单列', () => {
    window.resizeTo(375, 667);
    render(<PostList posts={mockPosts} />);
    
    const container = screen.getByTestId('post-list');
    expect(container).toHaveStyle({ 'grid-template-columns': '1fr' });
  });

  it('信息流在桌面端应为多列', () => {
    window.resizeTo(1440, 900);
    render(<PostList posts={mockPosts} />);
    
    const container = screen.getByTestId('post-list');
    expect(container).toHaveStyle({ 'grid-template-columns': 'repeat(3, 1fr)' });
  });
});
```

**响应式测试检查项：**

- 布局在不同断点下的正确性
- 图片和媒体的自适应缩放
- 触摸目标尺寸（最小44x44px）
- 文字可读性（最小字号12px）
- 导航模式切换（底部导航/侧边导航）
- 弹窗和抽屉的适配

---

## 3. 后端测试

### 3.1 API接口测试

**测试范围：**

- 所有RESTful API端点
- 请求参数验证
- 响应格式和状态码
- 错误处理和异常
- 分页和筛选
- 文件上传接口

**测试要点：**

```python
# 示例：信息列表API测试
import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_get_posts_success():
    """测试获取信息列表成功"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/posts?page=1&size=20")
        
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert len(data["items"]) <= 20

@pytest.mark.asyncio
async def test_get_posts_with_filters():
    """测试带筛选条件的信息列表"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get(
            "/api/posts?category_id=1&validity_status=valid&page=1"
        )
        
        assert response.status_code == 200
        data = response.json()
        # 验证返回的数据符合筛选条件
        for item in data["items"]:
            assert item["category_id"] == 1
            assert item["validity_status"] == "valid"

@pytest.mark.asyncio
async def test_get_posts_invalid_page():
    """测试无效页码参数"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/posts?page=0")
        
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

# 示例：创建信息API测试
@pytest.mark.asyncio
async def test_create_post_authenticated():
    """测试认证用户创建信息"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # 登录获取token
        login_response = await client.post(
            "/api/auth/login",
            json={"username": "testuser", "password": "Test1234"}
        )
        token = login_response.json()["access_token"]
        
        # 创建信息
        post_data = {
            "title": "测试标题",
            "description": "测试描述内容超过十个字符",
            "category_id": 1,
            "location_id": 1
        }
        response = await client.post(
            "/api/posts",
            json=post_data,
            headers={"Authorization": f"Bearer {token}"}
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["title"] == post_data["title"]
        assert data["author_id"] is not None

@pytest.mark.asyncio
async def test_create_post_unauthenticated():
    """测试未认证用户创建信息"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        post_data = {
            "title": "测试标题",
            "description": "测试描述内容超过十个字符",
            "category_id": 1,
            "location_id": 1
        }
        response = await client.post("/api/posts", json=post_data)
        
        assert response.status_code == 401

@pytest.mark.asyncio
async def test_create_post_invalid_data():
    """测试创建信息时数据验证"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # 标题过短
        post_data = {
            "title": "测试",  # 少于5个字符
            "description": "测试描述",
            "category_id": 1,
            "location_id": 1
        }
        response = await client.post("/api/posts", json=post_data)
        
        assert response.status_code == 422
```

**API测试检查项：**

- 正确的HTTP方法（GET、POST、PUT、DELETE）
- 请求参数验证（类型、长度、格式）
- 认证和授权检查
- 响应状态码（200、201、400、401、403、404、422、500）
- 响应数据结构
- 分页和排序
- 错误消息格式

### 3.2 业务逻辑测试

**测试范围：**

- 用户注册和登录逻辑
- 信息发布和编辑逻辑
- 有效性确认逻辑
- 权限控制逻辑
- 排序算法
- 通知生成逻辑

**测试要点：**

```python
# 示例：有效性确认逻辑测试
import pytest
from app.services.validity_service import ValidityService
from app.models import Post, ValidityConfirmation

@pytest.mark.asyncio
async def test_update_validity_status():
    """测试更新信息有效性状态"""
    # 准备测试数据
    post = Post(id=1, validity_status="uncertain")
    
    # 模拟确认数据
    confirmations = [
        ValidityConfirmation(post_id=1, status="valid"),
        ValidityConfirmation(post_id=1, status="valid"),
        ValidityConfirmation(post_id=1, status="expired"),
    ]
    
    # 调用服务
    new_status = ValidityService.calculate_status(confirmations)
    
    # 验证结果（2个有效，1个过期，应为有效）
    assert new_status == "valid"

@pytest.mark.asyncio
async def test_validity_status_possibly_expired():
    """测试信息可能过期状态"""
    confirmations = [
        ValidityConfirmation(post_id=1, status="valid"),
        ValidityConfirmation(post_id=1, status="uncertain"),
        ValidityConfirmation(post_id=1, status="uncertain"),
    ]
    
    new_status = ValidityService.calculate_status(confirmations)
    assert new_status == "possibly_expired"

# 示例：排序算法测试
def test_recommendation_scoring():
    """测试推荐排序算法"""
    from app.services.ranking_service import calculate_score
    
    post = Post(
        validity_status="valid",
        created_at=datetime.now() - timedelta(hours=2),
        like_count=10,
        comment_count=5,
        view_count=100
    )
    
    score = calculate_score(post)
    
    # 验证分数计算正确
    assert score > 0
    # 有效性得分权重0.3
    # 时间得分权重0.25
    # 互动得分权重0.15
    # 等等...

# 示例：权限控制测试
@pytest.mark.asyncio
async def test_user_can_only_edit_own_post():
    """测试用户只能编辑自己的信息"""
    user1 = User(id=1, username="user1")
    user2 = User(id=2, username="user2")
    post = Post(id=1, author_id=1, title="原标题")
    
    # user2尝试编辑user1的信息
    can_edit = PermissionService.can_edit_post(user2, post)
    assert can_edit is False
    
    # user1可以编辑自己的信息
    can_edit = PermissionService.can_edit_post(user1, post)
    assert can_edit is True

# 示例：敏感信息检测测试
def test_sensitive_info_detection():
    """测试敏感信息检测"""
    from app.services.content_service import detect_sensitive_info
    
    # 检测手机号
    text1 = "联系电话：13812345678"
    results = detect_sensitive_info(text1)
    assert "phone" in results
    
    # 检测身份证号
    text2 = "身份证号：110101199001011234"
    results = detect_sensitive_info(text2)
    assert "id_card" in results
    
    # 无敏感信息
    text3 = "这是一个普通的描述"
    results = detect_sensitive_info(text3)
    assert len(results) == 0
```

**业务逻辑测试检查项：**

- 业务规则正确性
- 边界条件和特殊情况
- 数据一致性
- 并发处理
- 事务完整性
- 错误处理和回滚

### 3.3 数据库测试

**测试范围：**

- 数据模型验证
- 数据库查询性能
- 事务处理
- 数据完整性约束
- 索引有效性
- 批量操作

**测试要点：**

```python
# 示例：数据库模型测试
import pytest
from sqlalchemy import select
from app.models import User, Post, Comment
from app.database import async_session

@pytest.mark.asyncio
async def test_user_model_constraints():
    """测试用户模型约束"""
    async with async_session() as session:
        # 测试用户名唯一性
        user1 = User(username="testuser", email="test1@example.com")
        session.add(user1)
        await session.commit()
        
        user2 = User(username="testuser", email="test2@example.com")
        session.add(user2)
        
        with pytest.raises(IntegrityError):
            await session.commit()

@pytest.mark.asyncio
async def test_post_soft_delete():
    """测试信息软删除"""
    async with async_session() as session:
        post = Post(id=1, title="测试", is_deleted=False)
        session.add(post)
        await session.commit()
        
        # 软删除
        post.is_deleted = True
        post.deleted_at = datetime.now()
        await session.commit()
        
        # 验证软删除后查询
        result = await session.execute(
            select(Post).where(Post.id == 1, Post.is_deleted == False)
        )
        assert result.scalar_one_or_none() is None

@pytest.mark.asyncio
async def test_cascade_delete():
    """测试级联删除"""
    async with async_session() as session:
        # 创建信息及其关联数据
        post = Post(id=1, title="测试")
        comment = Comment(post_id=1, content="评论")
        like = Like(post_id=1, user_id=1)
        
        session.add_all([post, comment, like])
        await session.commit()
        
        # 删除信息
        await session.delete(post)
        await session.commit()
        
        # 验证关联数据也被删除
        comments = await session.execute(
            select(Comment).where(Comment.post_id == 1)
        )
        assert comments.scalar_one_or_none() is None

# 示例：查询性能测试
@pytest.mark.asyncio
async def test_post_list_query_performance():
    """测试信息列表查询性能"""
    import time
    
    async with async_session() as session:
        start = time.time()
        
        result = await session.execute(
            select(Post)
            .where(Post.is_deleted == False)
            .where(Post.status == "published")
            .order_by(Post.created_at.desc())
            .limit(20)
        )
        posts = result.scalars().all()
        
        duration = time.time() - start
        
        # 查询应在100ms内完成
        assert duration < 0.1
        assert len(posts) <= 20
```

**数据库测试检查项：**

- 数据模型约束（唯一性、非空、外键）
- CRUD操作正确性
- 事务提交和回滚
- 级联操作
- 查询性能
- 索引使用
- 批量操作效率

### 3.4 认证测试

**测试范围：**

- 用户注册
- 用户登录
- JWT Token生成和验证
- Token刷新
- 登录失败锁定
- 密码重置
- 权限验证

**测试要点：**

```python
# 示例：认证流程测试
import pytest
from httpx import AsyncClient
from app.main import app
from app.core.security import create_access_token, verify_password

@pytest.mark.asyncio
async def test_user_registration():
    """测试用户注册"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "newuser",
                "email": "new@example.com",
                "password": "Test1234"
            }
        )
        
        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data
        assert data["username"] == "newuser"

@pytest.mark.asyncio
async def test_user_login():
    """测试用户登录"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # 先注册
        await client.post(
            "/api/auth/register",
            json={
                "username": "testuser",
                "email": "test@example.com",
                "password": "Test1234"
            }
        )
        
        # 登录
        response = await client.post(
            "/api/auth/login",
            json={
                "username": "testuser",
                "password": "Test1234"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

@pytest.mark.asyncio
async def test_login_failure_lockout():
    """测试登录失败锁定"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # 先注册
        await client.post(
            "/api/auth/register",
            json={
                "username": "lockuser",
                "email": "lock@example.com",
                "password": "Test1234"
            }
        )
        
        # 连续5次错误登录
        for i in range(5):
            await client.post(
                "/api/auth/login",
                json={
                    "username": "lockuser",
                    "password": "WrongPassword"
                }
            )
        
        # 第6次即使密码正确也应被锁定
        response = await client.post(
            "/api/auth/login",
            json={
                "username": "lockuser",
                "password": "Test1234"
            }
        )
        
        assert response.status_code == 429
        assert "locked" in response.json()["detail"].lower()

@pytest.mark.asyncio
async def test_token_refresh():
    """测试Token刷新"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # 登录获取token
        login_response = await client.post(
            "/api/auth/login",
            json={"username": "testuser", "password": "Test1234"}
        )
        refresh_token = login_response.json()["refresh_token"]
        
        # 刷新token
        response = await client.post(
            "/api/auth/refresh",
            json={"refresh_token": refresh_token}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["access_token"] != login_response.json()["access_token"]

@pytest.mark.asyncio
async def test_invalid_token():
    """测试无效Token"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get(
            "/api/users/me",
            headers={"Authorization": "Bearer invalid_token"}
        )
        
        assert response.status_code == 401

@pytest.mark.asyncio
async def test_expired_token():
    """测试过期Token"""
    import time
    
    # 创建已过期的token
    expired_token = create_access_token(
        data={"sub": "testuser"},
        expires_delta=timedelta(seconds=-1)
    )
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get(
            "/api/users/me",
            headers={"Authorization": f"Bearer {expired_token}"}
        )
        
        assert response.status_code == 401

@pytest.mark.asyncio
async def test_password_strength_validation():
    """测试密码强度验证"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # 弱密码（纯数字）
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "weakuser",
                "email": "weak@example.com",
                "password": "12345678"
            }
        )
        assert response.status_code == 422
        
        # 弱密码（太短）
        response = await client.post(
            "/api/auth/register",
            json={
                "username": "weakuser",
                "email": "weak@example.com",
                "password": "Test1"
            }
        )
        assert response.status_code == 422
```

**认证测试检查项：**

- 注册流程（用户名/邮箱唯一性、密码强度）
- 登录流程（正确凭证、错误凭证、锁定机制）
- Token生命周期（生成、验证、刷新、过期）
- 权限控制（角色验证、资源所有权）
- 安全机制（密码加密、Token存储）

---

## 4. 核心测试场景

### 4.1 测试场景清单

以下为核心测试场景，覆盖所有P0功能：

| 场景编号 | 场景名称 | 测试步骤 | 预期结果 | 优先级 |
|----------|----------|----------|----------|--------|
| TC001 | 游客浏览首页 | 1. 访问首页<br>2. 不登录浏览信息 | 显示推荐信息流，可正常浏览 | P0 |
| TC002 | 用户注册 | 1. 点击注册<br>2. 填写用户名、邮箱、密码<br>3. 提交注册 | 注册成功，自动登录并跳转到校园选择页 | P0 |
| TC003 | 用户登录 | 1. 点击登录<br>2. 输入用户名和密码<br>3. 提交登录 | 登录成功，跳转到首页 | P0 |
| TC004 | 登录失败锁定 | 1. 连续5次输入错误密码<br>2. 第6次输入正确密码 | 账户被锁定15分钟，提示用户 | P0 |
| TC005 | 校园选择 | 1. 首次登录后<br>2. 从列表选择校园<br>3. 确认选择 | 保存校园选择，跳转到首页 | P0 |
| TC006 | 浏览推荐信息流 | 1. 进入首页<br>2. 查看推荐信息 | 显示按综合排序的信息列表 | P0 |
| TC007 | 浏览最新信息流 | 1. 切换到"最新"标签<br>2. 查看信息列表 | 显示按时间倒序的信息列表 | P0 |
| TC008 | 分类筛选 | 1. 点击分类入口<br>2. 选择"校园美食"<br>3. 查看信息列表 | 只显示美食分类的信息 | P0 |
| TC009 | 关键词搜索 | 1. 点击搜索框<br>2. 输入"食堂"<br>3. 提交搜索 | 显示包含"食堂"的信息列表 | P0 |
| TC010 | 查看信息详情 | 1. 在列表中点击一条信息<br>2. 进入详情页 | 显示完整信息内容、图片、位置、有效性状态 | P0 |
| TC011 | 地图浏览 | 1. 进入地图页<br>2. 查看地图标记 | 显示信息标记，可缩放和拖动地图 | P0 |
| TC012 | 地图标记点击 | 1. 在地图上点击标记<br>2. 查看标记详情 | 显示信息摘要卡片 | P0 |
| TC013 | 发布信息 | 1. 点击发布按钮<br>2. 选择分类<br>3. 选择地点<br>4. 填写标题和描述<br>5. 上传图片<br>6. 提交发布 | 发布成功，跳转到详情页 | P0 |
| TC014 | 发布表单验证 | 1. 不填写必填字段<br>2. 提交表单 | 显示验证错误提示 | P0 |
| TC015 | 敏感信息检测 | 1. 在描述中输入手机号<br>2. 提交发布 | 提示检测到敏感信息 | P0 |
| TC016 | 编辑自己的信息 | 1. 进入自己发布的信息详情页<br>2. 点击编辑<br>3. 修改标题<br>4. 保存 | 修改成功，显示更新后的内容 | P0 |
| TC017 | 删除自己的信息 | 1. 进入自己发布的信息详情页<br>2. 点击删除<br>3. 确认删除 | 信息被软删除，从列表中移除 | P0 |
| TC018 | 点赞信息 | 1. 在信息卡片或详情页<br>2. 点击点赞按钮 | 点赞数+1，按钮状态改变 | P0 |
| TC019 | 取消点赞 | 1. 已点赞的信息<br>2. 再次点击点赞按钮 | 点赞数-1，按钮恢复原状 | P0 |
| TC020 | 收藏信息 | 1. 在信息卡片或详情页<br>2. 点击收藏按钮 | 收藏成功，按钮状态改变 | P0 |
| TC021 | 取消收藏 | 1. 已收藏的信息<br>2. 再次点击收藏按钮 | 取消收藏，按钮恢复原状 | P0 |
| TC022 | 发表评论 | 1. 在信息详情页<br>2. 输入评论内容<br>3. 提交评论 | 评论显示在评论区，评论数+1 | P0 |
| TC023 | 回复评论 | 1. 点击评论的回复按钮<br>2. 输入回复内容<br>3. 提交回复 | 回复显示在原评论下方 | P0 |
| TC024 | 删除自己的评论 | 1. 找到自己的评论<br>2. 点击删除<br>3. 确认删除 | 评论被删除，评论数-1 | P0 |
| TC025 | 确认信息有效性 | 1. 在信息详情页<br>2. 点击"仍然有效"<br>3. 确认 | 有效性统计更新，确认数+1 | P0 |
| TC026 | 标记信息失效 | 1. 在信息详情页<br>2. 点击"已经失效"<br>3. 确认 | 有效性统计更新，失效数+1 | P0 |
| TC027 | 查看个人中心 | 1. 进入个人中心页 | 显示用户信息、统计数据、快捷入口 | P0 |
| TC028 | 编辑个人资料 | 1. 进入个人中心<br>2. 点击编辑资料<br>3. 修改昵称<br>4. 保存 | 资料更新成功 | P0 |
| TC029 | 查看我的发布 | 1. 进入个人中心<br>2. 点击"我的发布" | 显示用户发布的所有信息列表 | P0 |
| TC030 | 查看我的收藏 | 1. 进入个人中心<br>2. 点击"我的收藏" | 显示用户收藏的所有信息列表 | P0 |
| TC031 | 查看消息通知 | 1. 点击通知图标<br>2. 进入通知页 | 显示未读和已读通知列表 | P0 |
| TC032 | 标记通知已读 | 1. 点击通知项<br>2. 跳转到相关内容 | 通知标记为已读，未读数-1 | P0 |
| TC033 | 举报内容 | 1. 在信息详情页<br>2. 点击举报<br>3. 选择举报类型<br>4. 填写说明<br>5. 提交举报 | 举报成功，提示等待审核 | P0 |
| TC034 | 管理员审核-通过 | 1. 进入审核后台<br>2. 查看待审核信息<br>3. 点击通过 | 信息状态变为已发布 | P0 |
| TC035 | 管理员审核-拒绝 | 1. 进入审核后台<br>2. 查看待审核信息<br>3. 点击拒绝<br>4. 填写拒绝原因 | 信息状态变为已拒绝，通知发布者 | P0 |
| TC036 | 移动端响应式 | 1. 使用移动设备访问<br>2. 浏览各页面 | 布局正确，触摸操作正常 | P0 |
| TC037 | 游客操作限制 | 1. 未登录状态<br>2. 尝试点赞/收藏/评论/发布 | 提示需要登录，跳转到登录页 | P0 |
| TC038 | 越权访问防护 | 1. 用户A登录<br>2. 尝试编辑用户B的信息 | 返回403错误，提示无权限 | P0 |
| TC039 | 图片上传 | 1. 在发布页<br>2. 选择图片文件<br>3. 等待上传完成 | 图片显示预览，上传成功 | P0 |
| TC040 | 图片上传限制 | 1. 上传超过5MB的图片<br>2. 上传非图片格式文件 | 提示文件大小或格式错误 | P0 |

### 4.2 测试场景优先级说明

**P0（必须测试）：**
- 核心用户流程（注册、登录、浏览、发布、互动）
- 安全相关场景（认证、授权、越权防护）
- 数据完整性场景（创建、编辑、删除）

**P1（应该测试）：**
- 边界条件和异常情况
- 性能相关场景
- 兼容性场景

**P2（可以测试）：**
- 用户体验优化场景
- 非核心功能场景

---

## 5. 验收标准

### 5.1 功能验收标准

**核心功能验收：**

| 验收项 | 验收标准 | 验证方法 |
|--------|----------|----------|
| 用户注册登录 | 用户可成功注册、登录，Token正确生成和验证 | 手动测试+自动化测试 |
| 校园选择 | 用户可选择校园，信息按校园组织 | 手动测试 |
| 信息浏览 | 游客和登录用户可浏览公开信息 | 手动测试 |
| 信息流 | 首页显示推荐和最新信息，分页正常 | 手动测试+自动化测试 |
| 地图功能 | 地图正确显示标记，可缩放拖动 | 手动测试 |
| 分类筛选 | 12个分类筛选功能正常 | 手动测试 |
| 搜索功能 | 关键词搜索返回正确结果 | 手动测试+自动化测试 |
| 信息详情 | 显示完整信息内容和元数据 | 手动测试 |
| 信息发布 | 用户可成功发布信息，表单验证正确 | 手动测试+自动化测试 |
| 信息编辑 | 用户可编辑自己的信息 | 手动测试 |
| 信息删除 | 用户可删除自己的信息，软删除正确 | 手动测试 |
| 点赞功能 | 点赞和取消点赞功能正常 | 手动测试+自动化测试 |
| 收藏功能 | 收藏和取消收藏功能正常 | 手动测试+自动化测试 |
| 评论功能 | 发表、回复、删除评论功能正常 | 手动测试+自动化测试 |
| 有效性确认 | 用户可确认信息有效性，统计正确 | 手动测试 |
| 个人中心 | 显示用户信息和统计数据 | 手动测试 |
| 我的发布 | 显示用户发布的信息列表 | 手动测试 |
| 我的收藏 | 显示用户收藏的信息列表 | 手动测试 |
| 消息通知 | 显示通知列表，标记已读正常 | 手动测试 |
| 举报功能 | 用户可举报违规内容 | 手动测试 |
| 管理审核 | 管理员可审核内容 | 手动测试 |

**功能完整性检查：**

- [ ] 所有P0功能已实现并可正常使用
- [ ] 核心用户闭环可走通（浏览→查看→发布→互动→验证）
- [ ] 错误处理和异常提示完善
- [ ] 数据一致性保证（删除信息时关联数据正确处理）

### 5.2 性能验收标准

**页面性能指标：**

| 指标 | 目标值 | 测量方法 | 说明 |
|------|--------|----------|------|
| 首次内容绘制（FCP） | ≤1.5秒 | Lighthouse | 首次显示内容的时间 |
| 最大内容绘制（LCP） | ≤2.5秒 | Lighthouse | 最大内容显示的时间 |
| 可交互时间（TTI） | ≤3.5秒 | Lighthouse | 页面可交互的时间 |
| 累计布局偏移（CLS） | ≤0.1 | Lighthouse | 布局稳定性 |
| 首次输入延迟（FID） | ≤100ms | Lighthouse | 首次交互响应时间 |

**API性能指标：**

| 接口类型 | 响应时间目标 | 并发要求 | 说明 |
|----------|--------------|----------|------|
| 列表查询 | ≤300ms | 100 QPS | 信息列表、评论列表等 |
| 详情查询 | ≤200ms | 200 QPS | 信息详情、用户详情等 |
| 创建操作 | ≤500ms | 50 QPS | 发布信息、发表评论等 |
| 更新操作 | ≤400ms | 50 QPS | 编辑信息、更新资料等 |
| 删除操作 | ≤300ms | 50 QPS | 删除信息、删除评论等 |
| 搜索接口 | ≤500ms | 100 QPS | 关键词搜索 |
| 文件上传 | ≤2秒 | 20 QPS | 图片上传 |

**性能测试场景：**

```
场景1：首页加载
- 100个并发用户
- 每个用户访问首页
- 验证响应时间≤2秒

场景2：信息流滚动
- 50个并发用户
- 每个用户滚动加载10页
- 验证无卡顿，响应时间≤500ms

场景3：发布高峰
- 20个并发用户
- 同时发布信息
- 验证无数据丢失，响应时间≤1秒

场景4：搜索压力
- 100个并发用户
- 同时执行搜索
- 验证响应时间≤1秒
```

**性能验收检查：**

- [ ] 页面加载时间≤2秒（4G网络）
- [ ] API响应时间≤500ms（P95）
- [ ] 系统支持100并发用户
- [ ] 无内存泄漏
- [ ] 数据库查询优化（无慢查询）

### 5.3 安全验收标准

**认证安全：**

| 验收项 | 验收标准 | 验证方法 |
|--------|----------|----------|
| 密码加密 | 使用bcrypt加密存储，成本因子≥12 | 代码审查+数据库检查 |
| Token安全 | JWT使用RS256算法，有效期合理 | 代码审查+Token解析 |
| 登录锁定 | 5次失败锁定15分钟 | 手动测试 |
| 密码强度 | 8位以上，含字母和数字 | 手动测试 |
| Token存储 | Access Token在内存，Refresh Token在HttpOnly Cookie | 代码审查 |

**接口安全：**

| 验收项 | 验收标准 | 验证方法 |
|--------|----------|----------|
| SQL注入防护 | 使用ORM参数化查询，无SQL拼接 | 代码审查+SQL注入测试 |
| XSS防护 | 输入过滤，输出转义，CSP配置 | 代码审查+XSS测试 |
| CSRF防护 | SameSite Cookie，Origin验证 | 代码审查+CSRF测试 |
| 权限控制 | 基于角色的权限验证，资源所有权验证 | 手动测试+自动化测试 |
| 接口限流 | 各接口配置限流策略 | 代码审查+压力测试 |

**数据安全：**

| 验收项 | 验收标准 | 验证方法 |
|--------|----------|----------|
| 敏感信息检测 | 发布时检测手机号、身份证等 | 手动测试 |
| 联系方式保护 | 默认不公开，部分隐藏 | 手动测试 |
| 位置隐私 | 坐标模糊化到100米 | 代码审查+数据库检查 |
| 数据删除 | 软删除机制，30天后物理删除 | 代码审查+数据库检查 |

**安全测试工具：**

- OWASP ZAP：自动化安全扫描
- SQLMap：SQL注入测试
- Burp Suite：接口安全测试
- 手动渗透测试

**安全验收检查：**

- [ ] 无严重安全漏洞（OWASP Top 10）
- [ ] 密码加密存储
- [ ] Token安全机制
- [ ] 权限控制正确
- [ ] 输入验证完善
- [ ] 敏感信息保护

### 5.4 兼容性验收标准

**浏览器兼容性：**

| 浏览器 | 版本要求 | 优先级 | 说明 |
|--------|----------|--------|------|
| Chrome | 最新2个版本 | P0 | 主要测试浏览器 |
| Safari | 最新2个版本 | P0 | iOS用户主要浏览器 |
| Firefox | 最新2个版本 | P1 | 部分用户使用 |
| Edge | 最新2个版本 | P1 | Windows用户 |
| 微信浏览器 | 最新版本 | P0 | 移动端重要入口 |

**设备兼容性：**

| 设备类型 | 屏幕尺寸 | 分辨率 | 测试重点 |
|----------|----------|--------|----------|
| 手机（小屏） | 320px-374px | 750x1334 | 布局适配，触摸操作 |
| 手机（标准） | 375px-413px | 750x1334-1125x2436 | 主要测试设备 |
| 手机（大屏） | 414px-428px | 1242x2688 | 大屏适配 |
| 平板 | 768px-1024px | 1536x2048 | 平板布局 |
| 桌面 | 1280px-1920px | 1920x1080 | 桌面布局 |

**操作系统兼容性：**

| 操作系统 | 版本要求 | 优先级 |
|----------|----------|--------|
| iOS | 14.0+ | P0 |
| Android | 8.0+ | P0 |
| Windows | 10+ | P1 |
| macOS | 10.15+ | P1 |

**兼容性测试检查：**

- [ ] 主流浏览器正常访问（Chrome、Safari、Firefox）
- [ ] 移动端触摸操作正常
- [ ] 不同屏幕尺寸布局正确
- [ ] 微信浏览器兼容性
- [ ] 横竖屏切换正常

### 5.5 用户体验验收标准

**界面设计：**

| 验收项 | 验收标准 | 说明 |
|--------|----------|------|
| 视觉一致性 | 符合设计规范，颜色、字体、间距统一 | 与设计稿对比 |
| 品牌识别 | Logo、色彩、风格符合品牌形象 | 手动检查 |
| 图标清晰 | 图标语义明确，尺寸合适 | 手动检查 |
| 图片质量 | 图片清晰，加载完整 | 手动检查 |

**交互体验：**

| 验收项 | 验收标准 | 说明 |
|--------|----------|------|
| 操作反馈 | 点击、加载、成功、失败都有反馈 | 手动测试 |
| 加载状态 | 显示加载动画或骨架屏 | 手动测试 |
| 错误提示 | 错误信息清晰，指导用户解决 | 手动测试 |
| 空状态 | 无数据时显示友好提示 | 手动测试 |
| 表单验证 | 实时验证，错误提示明确 | 手动测试 |

**可用性：**

| 验收项 | 验收标准 | 说明 |
|--------|----------|------|
| 导航清晰 | 用户可快速找到目标功能 | 用户测试 |
| 操作简洁 | 核心任务3步内完成 | 用户测试 |
| 文字易读 | 字号≥12px，对比度足够 | 手动检查 |
| 触摸目标 | 最小44x44px | 手动检查 |

**用户体验检查：**

- [ ] 界面美观，符合设计规范
- [ ] 交互流畅，无卡顿
- [ ] 错误提示友好
- [ ] 操作符合用户习惯
- [ ] 新手引导完善

---

## 6. 发布检查清单

### 6.1 发布前检查

**代码检查：**

- [ ] 所有代码已提交并合并到发布分支
- [ ] 代码审查已通过（至少2人审查）
- [ ] 无TODO或FIXME遗留
- [ ] 无调试代码（console.log、print等）
- [ ] 无敏感信息（密码、密钥、Token等）

**测试检查：**

- [ ] 单元测试全部通过（覆盖率≥75%）
- [ ] 集成测试全部通过
- [ ] E2E测试关键流程通过
- [ ] 性能测试达标
- [ ] 安全测试无严重漏洞
- [ ] 兼容性测试覆盖主流浏览器和设备

**文档检查：**

- [ ] API文档已更新
- [ ] 部署文档已更新
- [ ] 用户手册已更新（如需要）
- [ ] 变更日志已编写

**环境检查：**

- [ ] 生产环境配置已准备
- [ ] 数据库迁移脚本已准备
- [ ] 环境变量已配置
- [ ] 第三方服务配置已确认（邮件、存储等）

**备份检查：**

- [ ] 数据库已备份
- [ ] 配置文件已备份
- [ ] 回滚方案已准备

### 6.2 发布后验证

**功能验证：**

- [ ] 核心功能正常（注册、登录、浏览、发布、互动）
- [ ] 数据迁移成功（如有）
- [ ] 第三方服务连接正常（邮件、存储等）
- [ ] 定时任务正常运行（如有）

**性能验证：**

- [ ] 页面加载时间达标（≤2秒）
- [ ] API响应时间达标（≤500ms）
- [ ] 系统资源使用正常（CPU、内存、磁盘）
- [ ] 数据库性能正常（无慢查询）

**监控检查：**

- [ ] 日志系统正常（错误日志、访问日志）
- [ ] 监控告警配置完成
- [ ] 错误追踪系统正常（Sentry等）
- [ ] 性能监控正常（APM工具）

**安全检查：**

- [ ] SSL证书有效
- [ ] 安全头配置正确（CSP、HSTS等）
- [ ] 无异常访问记录
- [ ] 无安全告警

**业务验证：**

- [ ] 创建测试账号并验证完整流程
- [ ] 验证关键业务数据正确
- [ ] 验证通知系统正常（邮件、站内信）

### 6.3 回滚方案

**回滚条件：**

出现以下情况时考虑回滚：

- 核心功能不可用（注册、登录、发布等）
- 数据丢失或损坏
- 严重安全漏洞
- 性能严重下降（响应时间>5秒）
- 错误率超过5%

**回滚步骤：**

```
1. 决策回滚
   - 确认问题严重性
   - 通知相关人员
   - 决定回滚时间点

2. 停止服务
   - 停止应用服务
   - 显示维护页面
   - 通知用户

3. 恢复数据
   - 恢复数据库备份
   - 恢复配置文件
   - 恢复静态资源

4. 恢复服务
   - 启动应用服务
   - 验证服务正常
   - 移除维护页面

5. 验证确认
   - 验证核心功能正常
   - 验证数据完整性
   - 通知相关人员

6. 问题排查
   - 分析问题原因
   - 修复问题
   - 重新发布
```

**回滚时间目标：**

- 决策时间：≤10分钟
- 回滚执行：≤30分钟
- 验证确认：≤15分钟
- 总时间：≤1小时

---

**文档版本**：v1.0  
**创建日期**：2026-06-18  
**最后更新**：2026-06-18

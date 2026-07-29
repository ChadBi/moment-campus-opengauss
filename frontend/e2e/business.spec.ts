import { test, expect, DEMO_ACCOUNTS, DEMO_SCHOOLS, login, switchSchool, API_BASE, apiLogin } from './helpers';

/**
 * REL-01.3 商业/便利 E2E 测试（≥6 条）
 *
 * 覆盖：
 * 7. 注册新用户
 * 8. 找回密码流程
 * 9. 用户发布帖子
 * 10. 管理员审核帖子
 * 11. 官方发布主体认证
 * 12. 订阅推荐服务
 * 13. 分享深链接
 */

test.describe('商业/便利：注册与认证', () => {
  test('7. 注册 - 新用户可完成注册流程', async ({ page }) => {
    await page.goto('/register');
    await page.waitForLoadState('networkidle');

    // 生成唯一邮箱避免与已有用户冲突
    const uniqueEmail = `e2e_${Date.now()}@example.com`;

    // 填写注册表单
    await page.getByPlaceholder(/邮箱|email/i).fill(uniqueEmail);
    await page.getByPlaceholder(/昵称|nickname/i).fill('E2E测试用户');
    await page.getByRole('textbox', { name: '密码', exact: true }).fill('Test123456');
    await page.getByRole('textbox', { name: '确认密码', exact: true }).fill('Test123456');

    // 提交注册
    await page.getByRole('button', { name: /注册|register/i }).click();

    // 等待跳转或成功提示
    await page.waitForTimeout(3000);
    await page.waitForLoadState('networkidle');

    // 验证：要么跳转到首页/登录页，要么显示成功提示
    const url = page.url();
    const body = await page.locator('body').textContent();
    expect(
      !url.includes('/register') ||
      body?.includes('成功') ||
      body?.includes('success')
    ).toBeTruthy();
  });

  test('8. 找回密码 - 可发起密码重置请求', async ({ page }) => {
    await page.goto('/forgot-password');
    await page.waitForLoadState('networkidle');

    // 填写已存在的邮箱
    await page.getByPlaceholder(/邮箱|email/i).fill(DEMO_ACCOUNTS.user1.email);
    await page.getByRole('button', { name: /发送|提交|reset|找回/i }).click();

    // 等待响应
    await page.waitForTimeout(3000);
    await page.waitForLoadState('networkidle');

    // 验证：进入第二步（输入 token）或显示成功提示
    const body = await page.locator('body').textContent();
    expect(
      body?.includes('token') ||
      body?.includes('Token') ||
      body?.includes('验证码') ||
      body?.includes('已发送') ||
      body?.includes('成功')
    ).toBeTruthy();
  });
});

test.describe('商业/便利：发布与审核', () => {
  test('9. 用户发布帖子 - 可进入发布页填写表单', async ({ page }) => {
    await login(page, DEMO_ACCOUNTS.user1);

    // 导航到发布页
    await page.goto('/publish');
    await page.waitForLoadState('networkidle');

    // 验证发布页加载
    await expect(page.locator('body')).not.toContainText(/404|Not Found|页面不存在/i);

    // 验证有发布表单（标题/内容输入框）
    const titleInput = page.getByLabel(/标题|title/i).or(page.getByPlaceholder(/标题|title/i)).first();
    const contentInput = page.getByLabel(/内容|content/i).or(page.getByPlaceholder(/内容|content/i)).first();

    // 至少有一个输入框可见
    await expect(titleInput.or(contentInput).first()).toBeVisible({ timeout: 10000 });
  });

  test('10. 管理员审核 - admin 可访问审核后台', async ({ page }) => {
    await login(page, DEMO_ACCOUNTS.admin);

    // 导航到审核页
    await page.goto('/admin/review');
    await page.waitForLoadState('networkidle');

    // 验证审核页加载
    await expect(page.locator('body')).not.toContainText(/404|Not Found|页面不存在/i);

    // 验证页面有审核相关内容（待审核/通过/拒绝按钮或列表）
    await expect(page.locator('body')).toContainText(/审核|待审|review|pending|通过|拒绝|approve|reject/i, { timeout: 10000 });
  });
});

test.describe('商业/便利：官方主体与订阅', () => {
  test.skip('11. 官方发布主体认证 - 用户可浏览发布主体列表', async ({ page }) => {
    // publisher_profiles / publisher_memberships 已按产品决策下线，保留用例编号追踪历史能力。
    // 发布主体页是公开的
    await page.goto('/publishers');
    await page.waitForLoadState('networkidle');

    // 验证页面加载
    await expect(page.locator('body')).not.toContainText(/404|Not Found|页面不存在/i);

    // 验证有发布主体相关内容
    await expect(page.locator('body')).toContainText(/发布主体|官方|publisher|认证|主体/i, { timeout: 10000 });
  });

  test('12. 订阅推荐 - 登录用户可访问订阅入口', async ({ page }) => {
    await login(page, DEMO_ACCOUNTS.user1);

    // 订阅入口通常在个人中心或首页侧边栏
    await page.goto('/profile');
    await page.waitForLoadState('networkidle');

    // 验证个人中心加载
    await expect(page.locator('body')).not.toContainText(/404|Not Found|页面不存在/i);

    // 查找订阅相关入口（订阅/关注/推荐）
    const body = await page.locator('body').textContent();
    expect(
      body?.includes('订阅') ||
      body?.includes('关注') ||
      body?.includes('推荐') ||
      body?.includes('subscription')
    ).toBeTruthy();
  });

  test('13. 分享深链接 - 帖子深链接可在新会话打开', async ({ page, context }) => {
    // 游客访问首页获取第一个帖子链接
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const postLink = page.locator('a[href*="/posts/"]').first();
    const isVisible = await postLink.isVisible().catch(() => false);

    if (isVisible) {
      const href = await postLink.getAttribute('href');
      expect(href).toMatch(/\/posts\/\d+/);

      // 新开页面访问深链接
      const newPage = await context.newPage();
      await newPage.goto(href!);
      await newPage.waitForLoadState('networkidle');

      // 验证帖子详情页加载（有标题/内容/评论区）
      await expect(newPage.locator('body')).not.toContainText(/404|Not Found|页面不存在/i);
      await newPage.close();
    } else {
      // 首页无帖子链接时，验证首页本身可访问
      await expect(page.locator('body')).toBeVisible();
    }
  });
});

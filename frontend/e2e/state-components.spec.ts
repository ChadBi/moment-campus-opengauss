import { expect, test, type Page } from '@playwright/test';

const school = {
  id: 1,
  code: 'jiangnan',
  name: '江南大学',
  center_lat: 31.478,
  center_lng: 120.276,
  map_zoom: 16,
  is_active: true,
};

async function mockSchoolShell(page: Page) {
  await page.route('**/api/v1/schools', async (route) => {
    await route.fulfill({ json: [school] });
  });
}

async function mockAuthenticatedUser(page: Page, onboardingCompleted = true) {
  await page.addInitScript(
    ({ completed }) => {
      localStorage.setItem(
        'auth-storage',
        JSON.stringify({
          state: {
            accessToken: 'state-test-token',
            refreshToken: 'state-test-refresh',
            isAuthenticated: true,
            user: {
              id: 2,
              phone: '13900000002',
              education_email: 'user1@example.jiangnan.edu.cn',
              has_password: true,
              nickname: '状态测试用户',
              school_id: 1,
              role: 'user',
              onboarding_completed: completed,
            },
          },
          version: 0,
        })
      );
      localStorage.setItem(
        'campus-storage',
        JSON.stringify({
          state: {
            currentSchoolId: 1,
            currentSchoolCode: 'jiangnan',
            currentSchoolName: '江南大学',
            currentSchoolLogo: null,
            currentSchoolCenter: { lat: 31.478, lng: 120.276 },
            currentSchoolZoom: 16,
          },
          version: 0,
        })
      );
    },
    { completed: onboardingCompleted }
  );
  await page.route('**/api/v1/me/memberships', async (route) => {
    await route.fulfill({ json: [] });
  });
  await page.route('**/api/v1/notifications/unread-count', async (route) => {
    await route.fulfill({ json: { unread_count: 0, has_unread: false } });
  });
}

test.beforeEach(async ({ page }) => {
  await mockSchoolShell(page);
});

test('首页从统一加载态进入统一空态', async ({ page }) => {
  await page.route('**/api/v1/recommendations**', async (route) => {
    await route.fulfill({ json: { items: [], mode: null } });
  });
  await page.route('**/api/v1/posts**', async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 800));
    await route.fulfill({
      json: { items: [], total: 0, page: 1, page_size: 20, total_pages: 0, has_more: false },
    });
  });

  await page.goto('/?school=jiangnan');

  await expect(page.getByTestId('state-loading')).toContainText('正在加载校园此刻');
  await expect(page.getByTestId('state-empty')).toContainText('这里还没有校园经验');
  await expect(page.getByRole('button', { name: '发布第一条' })).toBeVisible();
});

test('专题列表错误态可原地重试并进入空态', async ({ page }) => {
  let attempts = 0;
  await page.route('**/api/v1/topics**', async (route) => {
    attempts += 1;
    if (attempts <= 2) {
      await route.fulfill({ status: 500, json: { detail: '专题服务暂时不可用' } });
      return;
    }
    await route.fulfill({
      json: { items: [], total: 0, page: 1, page_size: 20, total_pages: 0, has_more: false },
    });
  });

  await page.goto('/topics?school=jiangnan');

  await expect(page.getByTestId('state-error')).toContainText('专题服务暂时不可用');
  await page.getByRole('button', { name: '重新加载' }).click();
  await expect(page.getByTestId('state-empty')).toContainText('暂无专题内容');
  expect(attempts).toBe(3);
});

test('通知错误态可重试并进入空态', async ({ page }) => {
  await mockAuthenticatedUser(page);
  let attempts = 0;
  const notificationsPattern = /\/api\/v1\/notifications(?:\?.*)?$/;
  await page.route(notificationsPattern, async (route) => {
    attempts += 1;
    await route.fulfill({ status: 500, json: { detail: '通知加载失败' } });
  });

  await page.goto('/notifications?school=jiangnan');

  await expect(page.getByTestId('state-error')).toContainText('通知加载失败');
  await page.unroute(notificationsPattern);
  await page.route(notificationsPattern, async (route) => {
    attempts += 1;
    await route.fulfill({ json: { items: [], total: 0, page: 1, page_size: 20 } });
  });
  await page.getByRole('button', { name: '重新加载' }).click();
  await expect(page.getByTestId('state-empty')).toContainText('暂无通知');
  expect(attempts).toBeGreaterThanOrEqual(2);
});

test('发布元数据错误态可原地重试', async ({ page }) => {
  await mockAuthenticatedUser(page);
  let categoryAttempts = 0;
  await page.route('**/api/v1/categories', async (route) => {
    categoryAttempts += 1;
    if (categoryAttempts <= 2) {
      await route.fulfill({ status: 500, json: { detail: '分类加载失败' } });
      return;
    }
    await route.fulfill({
      json: [{ id: 1, name: '校园互助', code: 'share', icon: '互', sort_order: 1 }],
    });
  });
  await page.route('**/api/v1/locations', async (route) => {
    await route.fulfill({ json: [] });
  });

  await page.goto('/publish?school=jiangnan');

  await expect(page.getByTestId('state-error')).toContainText('分类加载失败');
  await page.getByRole('button', { name: '重新加载' }).click();
  await expect(page.getByRole('button', { name: /校园互助/ })).toBeVisible();
  expect(categoryAttempts).toBe(3);
});

test('首用引导元数据错误态可重试', async ({ page }) => {
  await mockAuthenticatedUser(page, false);
  let categoryAttempts = 0;
  const categoriesPattern = '**/api/v1/categories';
  await page.route(categoriesPattern, async (route) => {
    categoryAttempts += 1;
    await route.fulfill({ status: 500, json: { detail: '引导分类加载失败' } });
  });
  await page.route('**/api/v1/locations', async (route) => {
    await route.fulfill({ json: [] });
  });
  await page.route('**/api/v1/posts**', async (route) => {
    await route.fulfill({
      json: { items: [], total: 0, page: 1, page_size: 20, total_pages: 0, has_more: false },
    });
  });
  await page.route('**/api/v1/recommendations**', async (route) => {
    await route.fulfill({ json: { items: [], mode: null } });
  });

  await page.goto('/?school=jiangnan');
  await page.getByRole('button', { name: '下一步' }).click();

  await expect(page.getByTestId('state-error')).toContainText('引导分类加载失败');
  await page.unroute(categoriesPattern);
  await page.route(categoriesPattern, async (route) => {
    categoryAttempts += 1;
    await route.fulfill({
      json: [{ id: 1, name: '校园互助', code: 'share', icon: '互', sort_order: 1 }],
    });
  });
  await page.getByRole('button', { name: '重新加载' }).click();
  await expect(page.getByRole('button', { name: /校园互助/ })).toBeVisible();
  await expect(page.getByTestId('state-empty').filter({ hasText: '暂无可关注地点' })).toBeVisible();
  expect(categoryAttempts).toBeGreaterThanOrEqual(2);
});

test('详情评论错误态可独立重试并进入空态', async ({ page }) => {
  let commentAttempts = 0;
  await page.route(/\/api\/v1\/posts\/42(?:\?.*)?$/, async (route) => {
    await route.fulfill({
      json: {
        id: 42,
        title: '测试校园信息',
        content: '用于验证评论区状态。',
        status: 'published',
        author: { id: 1, nickname: '测试作者' },
        category: { id: 1, name: '校园互助' },
        location: null,
        images: [],
        view_count: 1,
        like_count: 0,
        comment_count: 0,
        is_anonymous: false,
        created_at: '2026-07-31T08:00:00Z',
        updated_at: '2026-07-31T08:00:00Z',
        governance: {
          total_validation_count: 0,
          confirmation_count: 0,
          refutation_count: 0,
          user_validation_type: null,
        },
      },
    });
  });
  await page.route('**/api/v1/posts/42/comments**', async (route) => {
    commentAttempts += 1;
    if (commentAttempts <= 2) {
      await route.fulfill({ status: 500, json: { detail: '评论加载失败' } });
      return;
    }
    await route.fulfill({ json: { items: [], total: 0, page: 1, page_size: 20 } });
  });

  await page.goto('/posts/42?school=jiangnan');

  await expect(page.getByRole('heading', { name: '测试校园信息' })).toBeVisible();
  await expect(page.getByTestId('state-error')).toContainText('评论加载失败');
  await page.getByRole('button', { name: '重新加载' }).click();
  await expect(page.getByTestId('state-empty')).toContainText('还没有评论');
  expect(commentAttempts).toBe(3);
});

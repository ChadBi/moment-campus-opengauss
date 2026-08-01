import { test, expect } from './helpers';

const schools = [
  { id: 1, code: 'jiangnan', name: '江南大学', center_lat: 31.48, center_lng: 120.27, map_zoom: 16 },
  { id: 2, code: 'fudan', name: '复旦大学', center_lat: 31.30, center_lng: 121.50, map_zoom: 16 },
];

const categories = {
  jiangnan: [{ id: 101, name: '江南分类', code: 'stable-code', icon: '甲', sort_order: 1 }],
  fudan: [{ id: 909, name: '复旦分类', code: 'stable-code', icon: '乙', sort_order: 1 }],
};

test.beforeEach(async ({ page }) => {
  await page.route('**/api/v1/schools', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(schools) });
  });
  await page.route('**/api/v1/locations', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: '[]' });
  });
});

test('搜索分类加载失败后可重试恢复', async ({ page }) => {
  let attempts = 0;
  let shouldFail = true;
  await page.route('**/api/v1/categories', async (route) => {
    attempts += 1;
    if (shouldFail) {
      await route.fulfill({ status: 500, contentType: 'application/json', body: '{"detail":"failed"}' });
      return;
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(categories.jiangnan) });
  });

  await page.goto('/search?school=jiangnan');
  await page.getByRole('button', { name: /^筛选/ }).click();
  await expect(page.getByRole('button', { name: '重试分类' })).toBeVisible();
  await expect(page.getByRole('option', { name: /江南分类/ })).toHaveCount(0);
  const failedAttempts = attempts;
  shouldFail = false;
  await page.getByRole('button', { name: '重试分类' }).click();
  await expect(page.getByRole('option', { name: /江南分类/ })).toHaveCount(1);
  expect(attempts).toBeGreaterThan(failedAttempts);
});

test('地图分类与 marker 错误均可重试恢复', async ({ page }) => {
  let categoryAttempts = 0;
  let markerAttempts = 0;
  let categoriesShouldFail = true;
  let markersShouldFail = true;
  await page.route('**/api/v1/categories', async (route) => {
    categoryAttempts += 1;
    if (categoriesShouldFail) {
      await route.fulfill({ status: 500, contentType: 'application/json', body: '{"detail":"failed"}' });
      return;
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(categories.jiangnan) });
  });
  await page.route('**/api/v1/map/markers**', async (route) => {
    markerAttempts += 1;
    if (markersShouldFail) {
      await route.fulfill({ status: 500, contentType: 'application/json', body: '{"detail":"failed"}' });
      return;
    }
    await route.fulfill({ status: 200, contentType: 'application/json', body: '{"markers":[]}' });
  });

  await page.goto('/map?school=jiangnan');
  await expect(page.getByRole('button', { name: '重试分类' })).toBeVisible();
  const failedCategoryAttempts = categoryAttempts;
  categoriesShouldFail = false;
  await page.getByRole('button', { name: '重试分类' }).click();
  await expect(page.getByRole('button', { name: '江南分类' })).toBeVisible();
  await expect(page.getByText('地图信息加载失败')).toBeVisible();
  const failedMarkerAttempts = markerAttempts;
  markersShouldFail = false;
  await page.getByText('地图信息加载失败').locator('..').getByRole('button', { name: '重试' }).click();
  await expect(page.getByText('地图信息加载失败')).toHaveCount(0);
  expect(categoryAttempts).toBeGreaterThan(failedCategoryAttempts);
  expect(markerAttempts).toBeGreaterThan(failedMarkerAttempts);
});

test('切换学校立即清除旧分类并按新学校请求', async ({ page }) => {
  const categoryHeaders: string[] = [];
  await page.route('**/api/v1/categories', async (route) => {
    const schoolCode = await route.request().headerValue('x-school-code') ?? '';
    categoryHeaders.push(schoolCode);
    if (schoolCode === 'fudan') await new Promise((resolve) => setTimeout(resolve, 500));
    const items = schoolCode === 'fudan' ? categories.fudan : categories.jiangnan;
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(items) });
  });
  await page.route('**/api/v1/map/markers**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: '{"markers":[]}' });
  });

  await page.goto('/map?school=jiangnan');
  const jiangnanButton = page.getByRole('button', { name: '江南分类' });
  await expect(jiangnanButton).toBeVisible();
  const jiangnanStyle = await jiangnanButton.getAttribute('style');
  await page.goto('/map?school=fudan');
  await expect(jiangnanButton).toHaveCount(0);
  await expect(page.getByText('分类加载中...')).toBeVisible();
  const fudanButton = page.getByRole('button', { name: '复旦分类' });
  await expect(fudanButton).toBeVisible();
  expect(await fudanButton.getAttribute('style')).toBe(jiangnanStyle);
  expect(categoryHeaders).toContain('jiangnan');
  expect(categoryHeaders).toContain('fudan');
});

import { test, expect, DEMO_ACCOUNTS, API_BASE, apiLogin, login } from './helpers';
import { spawnSync } from 'node:child_process';
import { resolve } from 'node:path';

const purgeCategory = (code: string) => {
  const backendDir = resolve(process.cwd(), '..', 'backend');
  const python = resolve(
    backendDir,
    process.platform === 'win32' ? '.venv/Scripts/python.exe' : '.venv/bin/python'
  );
  const script = `
import asyncio
import sys
from sqlalchemy import delete, select
from app.database import async_session_maker
from app.models.admin_operation_log import AdminOperationLog
from app.models.category import Category

async def main():
    async with async_session_maker() as db:
        category = await db.scalar(select(Category).where(Category.code == sys.argv[1]))
        if category is None:
            return
        await db.execute(delete(AdminOperationLog).where(AdminOperationLog.target_type == "category", AdminOperationLog.target_id == category.id))
        await db.delete(category)
        await db.commit()

asyncio.run(main())
`;
  const result = spawnSync(python, ['-c', script, code], {
    cwd: backendDir,
    env: { ...process.env, APP_ENV: 'opengauss' },
    encoding: 'utf8',
  });
  expect(result.status, result.stderr || result.stdout).toBe(0);
};

test('管理员分类变更无需重启同步到普通用户发布、搜索和地图', async ({ page, request }) => {
  const suffix = `${Date.now()}-${test.info().workerIndex}`;
  const code = `e2e_live_${suffix.replace(/\D/g, '')}`;
  const createdName = `E2E热同步-${suffix}`;
  const updatedName = `${createdName}-已修改`;
  const adminSession = await apiLogin(DEMO_ACCOUNTS.admin);
  const adminHeaders = {
    Authorization: `Bearer ${adminSession.access_token}`,
    'X-School-Code': 'jiangnan',
  };
  let categoryId: number | null = null;

  const expectOnUserPages = async (name: string, visible: boolean) => {
    await page.goto('/publish?school=jiangnan');
    const publishCategory = page.getByRole('button', { name: new RegExp(name) });
    await (visible ? expect(publishCategory).toBeVisible() : expect(publishCategory).toHaveCount(0));

    await page.goto('/search?school=jiangnan');
    await page.getByRole('button', { name: /^筛选/ }).click();
    const searchCategory = page.getByRole('option', { name: new RegExp(name) });
    await (visible ? expect(searchCategory).toHaveCount(1) : expect(searchCategory).toHaveCount(0));

    await page.goto('/map?school=jiangnan');
    const mapCategory = page.getByRole('button', { name });
    await (visible ? expect(mapCategory).toBeVisible() : expect(mapCategory).toHaveCount(0));
  };

  try {
    await login(page, DEMO_ACCOUNTS.admin);
    await page.goto('/admin/categories?school=jiangnan');
    await page.getByRole('button', { name: '新建分类' }).click();
    await page.getByPlaceholder('如：失物招领').fill(createdName);
    await page.getByPlaceholder('如：lost_found').fill(code);
    await page.getByPlaceholder('如：📦').fill('🧪');
    await page.getByRole('button', { name: '创建', exact: true }).click();
    await expect(page.getByText('分类创建成功')).toBeVisible();
    const createdResponse = await request.get(`${API_BASE}/admin/categories`, {
      headers: adminHeaders,
      params: { page: 1, page_size: 100 },
    });
    expect(createdResponse.ok()).toBeTruthy();
    const createdCategories = await createdResponse.json();
    categoryId = createdCategories.items.find((item: { code: string }) => item.code === code)?.id ?? null;
    expect(categoryId).not.toBeNull();

    await login(page, DEMO_ACCOUNTS.user1);
    await expectOnUserPages(createdName, true);

    await login(page, DEMO_ACCOUNTS.admin);
    await page.goto('/admin/categories?school=jiangnan');
    const createdRow = page.getByRole('row').filter({ hasText: code });
    await createdRow.getByTitle('编辑').click();
    await page.getByPlaceholder('如：失物招领').fill(updatedName);
    await page.getByRole('button', { name: '保存', exact: true }).click();
    await expect(page.getByText('分类更新成功')).toBeVisible();

    await login(page, DEMO_ACCOUNTS.user1);
    await expectOnUserPages(updatedName, true);
    await expect(page.getByText(createdName, { exact: true })).toHaveCount(0);

    await login(page, DEMO_ACCOUNTS.admin);
    await page.goto('/admin/categories?school=jiangnan');
    const updatedRow = page.getByRole('row').filter({ hasText: code });
    page.once('dialog', (dialog) => dialog.accept());
    await updatedRow.getByTitle('禁用').click();
    await expect(page.getByText(`分类「${updatedName}」已禁用`)).toBeVisible();

    await login(page, DEMO_ACCOUNTS.user1);
    await expectOnUserPages(updatedName, false);
  } finally {
    if (categoryId !== null) {
      const categoryResponse = await request.get(`${API_BASE}/admin/categories`, {
        headers: adminHeaders,
        params: { page: 1, page_size: 100, is_active: true },
      });
      if (categoryResponse.ok()) {
        const activeCategories = await categoryResponse.json();
        if (activeCategories.items.some((item: { id: number }) => item.id === categoryId)) {
          await request.delete(`${API_BASE}/admin/categories/${categoryId}`, { headers: adminHeaders });
        }
      }
    }
    purgeCategory(code);
  }
});

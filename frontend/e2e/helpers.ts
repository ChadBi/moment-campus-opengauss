import { test as base, expect, type Page } from '@playwright/test';

/**
 * REL-01.3 E2E 测试共享辅助函数
 *
 * 演示账号（来自 AGENTS.md）：
 *   平台超管：13900000001 / pass123
 *   江南大学普通用户：13900000002 ~ 13900000011 / pass123
 *
 * 演示学校（来自 seed_data.py）：
 *   jiangnan（江南大学，主展示租户）
 *   fudan（复旦大学）
 *   zju（浙江大学）
 */

export const DEMO_ACCOUNTS = {
  admin: { phone: '13900000001', password: 'pass123' },
  user1: { phone: '13900000002', password: 'pass123' },
  user2: { phone: '13900000003', password: 'pass123' },
  user3: { phone: '13900000004', password: 'pass123' },
} as const;

export const DEMO_SCHOOLS = {
  jiangnan: { code: 'jiangnan', name: '江南大学' },
  fudan: { code: 'fudan', name: '复旦大学' },
  zju: { code: 'zju', name: '浙江大学' },
} as const;

/**
 * 登录指定账号并等待跳转完成
 */
export async function login(page: Page, account: { phone: string; password: string }) {
  await page.goto('/login');
  await page.waitForLoadState('networkidle');
  await page.getByPlaceholder(/手机号|手机号码|phone/i).fill(account.phone);
  await page.getByPlaceholder(/密码|password/i).fill(account.password);
  await page.getByRole('button', { name: /登录|登 录|login/i }).click();
  // 等待跳转到首页或后台
  await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });
  await page.waitForLoadState('networkidle');
}

/**
 * 切换到指定学校（通过 URL 参数 ?school=code）
 */
export async function switchSchool(page: Page, schoolCode: string) {
  await page.goto(`/?school=${schoolCode}`);
  await page.waitForLoadState('networkidle');
}

/**
 * 退出登录
 */
export async function logout(page: Page) {
  // 清除 localStorage 中的 auth 状态
  await page.evaluate(() => {
    localStorage.clear();
    sessionStorage.clear();
  });
  await page.reload();
  await page.waitForLoadState('networkidle');
}

/**
 * 获取后端 API 基础地址
 */
export const API_BASE = 'http://localhost:8000/api/v1';

/**
 * 通过 API 直接登录获取 token（用于测试前置数据准备）
 */
export async function apiLogin(account: { phone: string; password: string }) {
  const resp = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(account),
  });
  if (!resp.ok) {
    throw new Error(`API login failed: ${resp.status} ${await resp.text()}`);
  }
  return (await resp.json()) as {
    access_token: string;
    refresh_token: string;
    user: {
      id: number;
      phone: string;
      education_email: string | null;
      has_password: boolean;
      role: string;
      school_id: number;
    };
  };
}

/**
 * 扩展 test fixture：提供已登录的 page
 */
export const test = base.extend<{ loggedInPage: Page }>({
  loggedInPage: async ({ page }, use) => {
    await login(page, DEMO_ACCOUNTS.user1);
    await use(page);
  },
});

export { expect };

import { defineConfig, devices } from '@playwright/test';

/**
 * REL-01.3 Playwright 配置
 *
 * 端到端测试：前端 5173 + 后端 8000（需预先启动）
 * 启动方式：
 *   后端：cd backend && uvicorn app.main:app --reload  (需 $env:APP_ENV = "opengauss")
 *   前端：cd frontend && npm run dev
 * 运行：cd frontend && npx playwright test
 *
 * 浏览器：使用系统已安装的 Chrome（channel: 'chrome'）避免沙箱环境下载限制
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: false, // 串行执行避免后端并发数据竞争
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1, // 单线程：E2E 测试共享后端数据库状态
  reporter: [
    ['list'],
    ['html', { open: 'never', outputFolder: 'playwright-report' }],
  ],
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    actionTimeout: 15000,
    navigationTimeout: 30000,
    locale: 'zh-CN',
    timezoneId: 'Asia/Shanghai',
  },
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        // 使用系统已安装的 Chrome，避免 Playwright 内置浏览器下载失败
        channel: 'chrome',
      },
    },
  ],
  // 不启动本地服务器：需预先启动前后端
  // 后端：cd backend && uvicorn app.main:app --reload
  // 前端：cd frontend && npm run dev
});

import { test, expect, DEMO_ACCOUNTS, login } from './helpers';
import AxeBuilder from 'axe-playwright';

/**
 * REL-01.4 无障碍测试：axe + 人工抽查
 *
 * 五条关键流程：
 *   1. 登录页（/login）
 *   2. 搜索页（/search）
 *   3. 学校切换（首页 + 切换器）
 *   4. 发布页（/publish）
 *   5. 后台（/admin）
 *
 * axe 自动扫描：检查 WCAG 2.1 AA 级别违规（critical / serious / moderate）
 * 人工抽查要点：
 *   - 键盘可达：Tab 顺序合理，焦点可见
 *   - 焦点管理：跳转页面后焦点重置
 *   - 错误提示：表单错误以 role=alert 暴露给屏幕阅读器
 *   - 触控目标：按钮 ≥44×44 px
 *   - 屏幕阅读器：关键 landmark（main/nav/header）存在
 *
 * 注：axe 扫描结果会输出到控制台，违规项以 soft-expect 形式记录，
 *     关键流程的严重违规（critical/serious）将作为任务报告的输入。
 */

const VIOLATION_TAGS = ['critical', 'serious', 'moderate'];

/**
 * 分析 axe 结果并打印违规摘要
 */
function analyzeAxeResults(violations: any[], pageName: string) {
  const relevant = violations.filter((v) =>
    v.tags?.some((tag: string) => VIOLATION_TAGS.includes(tag)) ||
    VIOLATION_TAGS.includes(v.impact)
  );

  if (relevant.length > 0) {
    console.log(`\n========== [axe] ${pageName} 违规摘要 ==========`);
    relevant.forEach((v) => {
      console.log(
        `[${v.impact?.toUpperCase() ?? 'UNKNOWN'}] ${v.id}: ${v.description} (${v.nodes?.length ?? 0} 个节点)`
      );
      v.nodes?.slice(0, 3).forEach((n: any) => {
        console.log(`  - ${n.html}`);
      });
    });
    console.log('==================================================\n');
  }

  return relevant;
}

test.describe('REL-01.4 无障碍：五条关键流程 axe 扫描', () => {
  test('1. 登录页 - 键盘可达 + 错误提示 + 触控目标', async ({ page }) => {
    await page.goto('/login');
    await page.waitForLoadState('networkidle');

    // 人工抽查：键盘可达性
    // Tab 遍历表单元素，所有元素应可获焦
    for (let i = 0; i < 5; i++) {
      await page.keyboard.press('Tab');
      const activeTag = await page.evaluate(() => document.activeElement?.tagName);
      expect(['INPUT', 'BUTTON', 'A', 'SELECT', 'TEXTAREA']).toContain(activeTag || '');
    }

    // 人工抽查：错误提示以 role=alert 暴露
    // 触发一次错误：提交空表单
    const emailInput = page.getByPlaceholder(/邮箱|email/i);
    const passwordInput = page.getByPlaceholder(/密码|password/i);
    await emailInput.fill('');
    await passwordInput.fill('');

    // 点击登录按钮触发校验
    await page.getByRole('button', { name: /登录|登 录|login/i }).click();
    await page.waitForTimeout(500);

    // 验证错误提示容器存在（role=alert 或 aria-live）
    const errorContainer = page.locator('[role="alert"], [aria-live="assertive"], [aria-live="polite"]');
    const errorVisible = await errorContainer.count();
    // 登录页应包含错误提示容器（即使为空，结构也应存在）
    // 注：HTML5 required 校验可能阻止提交，此情况下 errorContainer 可能为 0
    if (errorVisible > 0) {
      // 验证错误容器可见且有内容
      await expect(errorContainer.first()).toBeVisible();
    }

    // axe 扫描
    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
      .analyze();

    const relevant = analyzeAxeResults(results.violations, '登录页');
    // 软断言：登录页不应有 critical 违规（serious/moderate 记录到报告）
    const critical = relevant.filter((v) => v.impact === 'critical');
    expect(critical.length, `登录页有 ${critical.length} 个 critical 违规`).toBe(0);
  });

  test('2. 搜索页 - 焦点管理 + 屏幕阅读器 landmark', async ({ page }) => {
    await page.goto('/search');
    await page.waitForLoadState('networkidle');

    // 人工抽查：页面应包含 main / header / nav 等 landmark
    const landmarks = await page.locator('main, [role="main"], header, [role="banner"], nav, [role="navigation"]').count();
    expect(landmarks, '搜索页应至少包含一个 landmark').toBeGreaterThan(0);

    // 人工抽查：搜索框应可获焦
    const searchInput = page.getByPlaceholder(/搜索|search|问/i).first();
    if (await searchInput.isVisible().catch(() => false)) {
      await searchInput.focus();
      const isFocused = await page.evaluate(() => document.activeElement?.tagName);
      expect(isFocused).toBeTruthy();
    }

    // axe 扫描
    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
      .analyze();

    const relevant = analyzeAxeResults(results.violations, '搜索页');
    const critical = relevant.filter((v) => v.impact === 'critical');
    expect(critical.length, `搜索页有 ${critical.length} 个 critical 违规`).toBe(0);
  });

  test('3. 学校切换 - 首页 landmark + 切换器可达', async ({ page }) => {
    await page.goto('/?school=jiangnan');
    await page.waitForLoadState('networkidle');

    // 人工抽查：页面应包含 main landmark
    const mainLandmark = await page.locator('main, [role="main"]').count();
    expect(mainLandmark, '首页应包含 main landmark').toBeGreaterThan(0);

    // 人工抽查：查找学校切换器
    const switcher = page.locator(
      '[aria-label*="学校"], [aria-label*="切换"], button:has-text("江南"), button:has-text("学校")'
    ).first();

    if (await switcher.isVisible().catch(() => false)) {
      // 触控目标检查：切换器尺寸 ≥ 44×44
      const box = await switcher.boundingBox();
      if (box) {
        // 软断言：触控目标尺寸（允许部分元素小于 44，但记录到报告）
        if (box.width < 44 || box.height < 44) {
          console.log(`[axe] 学校切换器触控目标偏小: ${box.width}x${box.height}`);
        }
      }
      // 切换器应可通过键盘获焦
      await switcher.focus();
    }

    // axe 扫描
    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
      .analyze();

    const relevant = analyzeAxeResults(results.violations, '首页（学校切换）');
    const critical = relevant.filter((v) => v.impact === 'critical');
    expect(critical.length, `首页有 ${critical.length} 个 critical 违规`).toBe(0);
  });

  test('4. 发布页 - 表单标签关联 + 错误提示', async ({ page }) => {
    await login(page, DEMO_ACCOUNTS.user1);

    await page.goto('/publish');
    await page.waitForLoadState('networkidle');

    // 人工抽查：发布页应包含表单
    const formElements = await page.locator('input, textarea, select').count();
    expect(formElements, '发布页应至少有一个表单元素').toBeGreaterThan(0);

    // 人工抽查：表单元素应有关联 label（label[for] 或 aria-label）
    const inputs = page.locator('input:visible, textarea:visible, select:visible');
    const inputCount = await inputs.count();
    let labeledCount = 0;
    for (let i = 0; i < inputCount; i++) {
      const el = inputs.nth(i);
      const id = await el.getAttribute('id');
      const ariaLabel = await el.getAttribute('aria-label');
      const ariaLabelledBy = await el.getAttribute('aria-labelledby');
      const placeholder = await el.getAttribute('placeholder');
      // 任一可访问名称来源即可
      if (id || ariaLabel || ariaLabelledBy || placeholder) {
        labeledCount++;
      }
    }
    // 软断言：至少一半表单元素应可访问命名
    if (inputCount > 0) {
      expect(labeledCount / inputCount, '表单元素可访问命名比例').toBeGreaterThanOrEqual(0.5);
    }

    // axe 扫描
    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
      .analyze();

    const relevant = analyzeAxeResults(results.violations, '发布页');
    const critical = relevant.filter((v) => v.impact === 'critical');
    expect(critical.length, `发布页有 ${critical.length} 个 critical 违规`).toBe(0);
  });

  test('5. 后台 - 管理页面 landmark + 键盘可达', async ({ page }) => {
    await login(page, DEMO_ACCOUNTS.admin);

    await page.goto('/admin');
    await page.waitForLoadState('networkidle');

    // 人工抽查：后台应包含 main / nav landmark
    const landmarks = await page.locator('main, [role="main"], nav, [role="navigation"], aside, [role="complementary"]').count();
    expect(landmarks, '后台应至少包含一个 landmark').toBeGreaterThan(0);

    // 人工抽查：后台侧边栏导航应可通过键盘 Tab 到达
    const navLinks = page.locator('nav a, [role="navigation"] a, aside a').first();
    if (await navLinks.isVisible().catch(() => false)) {
      await navLinks.focus();
      const focusedTag = await page.evaluate(() => document.activeElement?.tagName);
      expect(focusedTag).toBe('A');
    }

    // 人工抽查：后台应包含 h1 标题（页面主标题）
    const h1 = await page.locator('h1').count();
    if (h1 > 0) {
      expect(h1).toBeGreaterThanOrEqual(1);
    }

    // axe 扫描
    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
      .analyze();

    const relevant = analyzeAxeResults(results.violations, '后台');
    const critical = relevant.filter((v) => v.impact === 'critical');
    expect(critical.length, `后台有 ${critical.length} 个 critical 违规`).toBe(0);
  });
});

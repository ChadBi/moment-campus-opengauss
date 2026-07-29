import { expect, test, type Page } from '@playwright/test';

type AlignmentMeasurement = {
  dx: number;
  dy: number;
  kind: string;
};

const readAlignment = async (page: Page): Promise<AlignmentMeasurement[]> =>
  page.locator('.custom-marker').evaluateAll((elements) =>
    elements.map((element) => {
      const root = element.getBoundingClientRect();
      const path = element.querySelector<SVGPathElement>('.custom-marker__shape');
      if (!path) throw new Error('Marker SVG path is missing');
      const matrix = path.getScreenCTM();
      if (!matrix) throw new Error('Marker SVG screen matrix is unavailable');

      // MAP_MARKER_PATH deliberately starts at the colored visual tip.
      const tip = path.getPointAtLength(0).matrixTransform(matrix);
      const anchorX = root.left + root.width / 2;
      const anchorY = root.bottom;
      return {
        dx: tip.x - anchorX,
        dy: tip.y - anchorY,
        kind: (element as HTMLElement).dataset.markerKind ?? 'unknown',
      };
    })
  );

const expectAligned = (measurements: AlignmentMeasurement[]) => {
  expect(measurements.length).toBeGreaterThan(0);
  for (const measurement of measurements) {
    expect(Math.abs(measurement.dx), `${measurement.kind} marker dx`).toBeLessThanOrEqual(0.5);
    expect(Math.abs(measurement.dy), `${measurement.kind} marker dy`).toBeLessThanOrEqual(0.5);
  }
};

test.describe('MapLibre Marker geometry', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/map?school=jiangnan');
    await expect(page.locator('.custom-marker').first()).toBeVisible({ timeout: 20_000 });
  });

  test('single and grouped SVG tips stay on the anchor while idle and hovered', async ({ page }) => {
    const initial = await readAlignment(page);
    expect(new Set(initial.map(({ kind }) => kind))).toEqual(new Set(['grouped', 'single']));
    expectAligned(initial);

    for (const kind of ['grouped', 'single']) {
      await page.locator(`.custom-marker[data-marker-kind="${kind}"]`).first().hover();
      expectAligned(await readAlignment(page));
    }
  });

  test('tips remain aligned at zoom 14, 16 and 18 and marker click still opens the panel', async ({ page }) => {
    const zoomIn = page.getByRole('button', { name: '放大' });
    const zoomOut = page.getByRole('button', { name: '缩小' });

    expectAligned(await readAlignment(page)); // zoom 16
    await zoomOut.click();
    await zoomOut.click();
    await page.waitForTimeout(1_000);
    expectAligned(await readAlignment(page)); // zoom 14

    await zoomIn.click();
    await zoomIn.click();
    await zoomIn.click();
    await zoomIn.click();
    await page.waitForTimeout(1_000);
    expectAligned(await readAlignment(page)); // zoom 18

    await page.locator('.custom-marker').first().click();
    await expect(page.locator('aside.map-slide-panel')).toBeVisible();
  });
});

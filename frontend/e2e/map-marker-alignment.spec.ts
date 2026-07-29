import { expect, test, type Page } from '@playwright/test';

const SOURCE_ID = 'campus-post-markers';
const LAYER_ID = 'campus-post-marker-symbols';

const waitForMarkerLayer = async (page: Page, locationName?: string) => {
  await page.waitForFunction(
    ({ sourceId, expectedLocation }) => {
      const map = (window as typeof window & { __momentCampusMap?: any }).__momentCampusMap;
      if (!map?.isStyleLoaded() || !map.getSource(sourceId)) return false;
      const features = map.querySourceFeatures(sourceId);
      return expectedLocation
        ? features.some((feature: any) => feature.properties?.locationName === expectedLocation)
        : features.length > 0;
    },
    { sourceId: SOURCE_ID, expectedLocation: locationName },
    { timeout: 20_000 },
  );
};

test.describe('MapLibre native marker layer alignment', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/map?school=jiangnan');
    await waitForMarkerLayer(page);
  });

  test('single and grouped pins are rendered by the same WebGL canvas as AMap tiles', async ({ page }) => {
    const result = await page.evaluate(({ sourceId, layerId }) => {
      const map = (window as typeof window & { __momentCampusMap?: any }).__momentCampusMap;
      const features = map.querySourceFeatures(sourceId);
      return {
        canvasCount: document.querySelectorAll('.maplibregl-canvas').length,
        legacyDomMarkerCount: document.querySelectorAll('.custom-marker').length,
        counts: features.map((feature: any) => Number(feature.properties?.count)),
        anchor: map.getLayoutProperty(layerId, 'icon-anchor'),
        overlap: map.getLayoutProperty(layerId, 'icon-allow-overlap'),
      };
    }, { sourceId: SOURCE_ID, layerId: LAYER_ID });

    expect(result.canvasCount).toBe(1);
    expect(result.legacyDomMarkerCount).toBe(0);
    expect(result.counts.some((count: number) => count === 1)).toBe(true);
    expect(result.counts.some((count: number) => count > 1)).toBe(true);
    expect(result.anchor).toBe('bottom');
    expect(result.overlap).toBe(true);
  });

  test('every visible feature remains queryable at its projected anchor through zoom 14/16/18', async ({ page }) => {
    const checks = await page.evaluate(async ({ sourceId, layerId }) => {
      const map = (window as typeof window & { __momentCampusMap?: any }).__momentCampusMap;
      const features = map.querySourceFeatures(sourceId);
      const results: Array<{ zoom: number; visible: number; aligned: number }> = [];
      for (const zoom of [14, 16, 18]) {
        map.jumpTo({ zoom });
        await new Promise<void>((resolve) => map.once('render', () => resolve()));
        let visible = 0;
        let aligned = 0;
        for (const feature of features) {
          const point = map.project(feature.geometry.coordinates);
          if (point.x < 0 || point.y < 0 || point.x > map.getCanvas().width || point.y > map.getCanvas().height) continue;
          visible += 1;
          const rendered = map.queryRenderedFeatures(
            [[point.x - 2, point.y - 3], [point.x + 2, point.y]],
            { layers: [layerId] },
          );
          if (rendered.some((item: any) => item.properties?.groupKey === feature.properties?.groupKey)) aligned += 1;
        }
        results.push({ zoom, visible, aligned });
      }
      return results;
    }, { sourceId: SOURCE_ID, layerId: LAYER_ID });

    for (const check of checks) {
      expect(check.visible, `zoom ${check.zoom} visible features`).toBeGreaterThan(0);
      expect(check.aligned, `zoom ${check.zoom} anchors`).toBe(check.visible);
    }
  });

  test('the three reported stable canteens and their neighboring points share one exact zoom transform', async ({ page }) => {
    const schools = [
      { code: 'jiangnan', name: '江南大学', baseline: '第二食堂', coordinate: [120.275560, 31.479920] },
      { code: 'fudan', name: '复旦大学', baseline: '本部食堂', coordinate: [121.503900, 31.298650] },
      { code: 'zju', name: '浙江大学', baseline: '西区食堂', coordinate: [120.076500, 30.306500] },
    ];

    for (const school of schools) {
      await page.goto(`/map?school=${school.code}`);
      await expect(page.getByRole('button', { name: new RegExp(`当前学校：${school.name}`) })).toBeVisible();
      await page.evaluate((center) => {
        const map = (window as typeof window & { __momentCampusMap?: any }).__momentCampusMap;
        map.jumpTo({ center, zoom: 16 });
      }, school.coordinate);
      await waitForMarkerLayer(page, school.baseline);
      const result = await page.evaluate(({ sourceId, baselineName }) => {
        const map = (window as typeof window & { __momentCampusMap?: any }).__momentCampusMap;
        const features = map.querySourceFeatures(sourceId);
        const baseline = features.find((feature: any) => feature.properties?.locationName === baselineName);
        if (!baseline) throw new Error(`Missing baseline ${baselineName}`);
        const snapshots = [14, 16, 18].map((zoom) => {
          map.jumpTo({ zoom });
          const origin = map.project(baseline.geometry.coordinates);
          return new Map(features.map((feature: any) => {
            const point = map.project(feature.geometry.coordinates);
            return [feature.properties.groupKey, {
              x: (point.x - origin.x) / 2 ** zoom,
              y: (point.y - origin.y) / 2 ** zoom,
            }];
          }));
        });
        let maxError = 0;
        for (const [key, initial] of snapshots[0]) {
          for (const snapshot of snapshots.slice(1)) {
            const current = snapshot.get(key);
            maxError = Math.max(maxError, Math.abs(current.x - initial.x), Math.abs(current.y - initial.y));
          }
        }
        return { featureCount: features.length, maxError };
      }, { sourceId: SOURCE_ID, baselineName: school.baseline });

      expect(result.featureCount, `${school.code} feature count`).toBeGreaterThan(1);
      expect(result.maxError, `${school.code} normalized relative drift`).toBeLessThanOrEqual(0.5);
    }
  });

  test('hover keeps the geographic anchor fixed and clicking a symbol opens the existing panel', async ({ page }) => {
    const target = await page.evaluate(({ sourceId }) => {
      const map = (window as typeof window & { __momentCampusMap?: any }).__momentCampusMap;
      const feature = map.querySourceFeatures(sourceId)[0];
      const point = map.project(feature.geometry.coordinates);
      return { x: point.x, y: point.y, count: Number(feature.properties.count) };
    }, { sourceId: SOURCE_ID });
    const container = await page.locator('.maplibregl-map').boundingBox();
    if (!container) throw new Error('Map container is unavailable');

    const bodyY = container.y + target.y - (target.count > 1 ? 22 : 17);
    await page.mouse.move(container.x + target.x, bodyY);
    const anchorAfterHover = await page.evaluate(({ sourceId }) => {
      const map = (window as typeof window & { __momentCampusMap?: any }).__momentCampusMap;
      const feature = map.querySourceFeatures(sourceId)[0];
      return map.project(feature.geometry.coordinates);
    }, { sourceId: SOURCE_ID });
    expect(anchorAfterHover.x).toBeCloseTo(target.x, 6);
    expect(anchorAfterHover.y).toBeCloseTo(target.y, 6);

    await page.mouse.click(container.x + target.x, bodyY);
    await expect(page.locator('aside.map-slide-panel')).toBeVisible();
  });

  test('browser WGS-84 geolocation is converted to the GCJ-02 map contract', async ({ page, context }) => {
    await context.grantPermissions(['geolocation'], { origin: 'http://localhost:5173' });
    await context.setGeolocation({
      latitude: 31.48560159175487,
      longitude: 120.26658886699913,
    });

    const markerRequest = page.waitForRequest((request) => request.url().includes('/map/markers?'));
    await page.getByRole('button', { name: '定位' }).click();
    const request = await markerRequest;
    const url = new URL(request.url());
    const centerLatitude =
      (Number(url.searchParams.get('north')) + Number(url.searchParams.get('south'))) / 2;
    const centerLongitude =
      (Number(url.searchParams.get('east')) + Number(url.searchParams.get('west'))) / 2;

    expect(centerLatitude).toBeCloseTo(31.483652, 3);
    expect(centerLongitude).toBeCloseTo(120.271160, 3);
  });
});

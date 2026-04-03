import { test, expect } from '@playwright/test';

const PAGES = [
  { name: 'dashboard', label: 'Dashboard' },
  { name: 'validate', label: 'Validate' },
  { name: 'pipeline', label: 'Pipeline' },
  { name: 'tests', label: 'Tests' },
  { name: 'compare', label: 'Compare' },
  { name: 'rules', label: 'Rules' },
  { name: 'onboard', label: 'Onboard' },
  { name: 'config', label: 'Config' },
];

test.describe('Portal smoke tests', () => {
  for (const page of PAGES) {
    test(`${page.label} page loads without errors`, async ({ page: pw }) => {
      const errors: string[] = [];
      pw.on('pageerror', (err) => errors.push(err.message));

      await pw.goto(`/#${page.name}`);
      await pw.waitForTimeout(2000);

      // Page should have rendered content (not blank)
      const body = await pw.locator('body').textContent();
      expect(body?.trim().length).toBeGreaterThan(0);

      // No JS errors
      expect(errors).toEqual([]);
    });
  }

  test('Dashboard shows manifest stats', async ({ page }) => {
    await page.goto('/#dashboard');
    await page.waitForTimeout(2000);
    const text = await page.locator('body').textContent();
    // Should display counts
    expect(text).toContain('26');
  });

  test('Compare page shows regional_health_810 profile', async ({ page }) => {
    await page.goto('/#compare');
    await page.waitForTimeout(2000);
    const text = await page.locator('body').textContent();
    expect(text).toContain('regional_health_810');
  });

  test('Compare page shows Run 87 data', async ({ page }) => {
    await page.goto('/#compare');
    await page.waitForTimeout(2000);

    // Select regional_health_810 profile if there's a select element
    const select = page.locator('select').first();
    if (await select.isVisible()) {
      await select.selectOption({ label: /regional_health/i }).catch(() => {
        // Try by value
        return select.selectOption('regional_health_810');
      });
      await page.waitForTimeout(2000);
    }

    const text = await page.locator('body').textContent();
    // Run 87 should appear
    expect(text).toContain('87');
  });

  test('Rules page shows transaction and partner tiers', async ({ page }) => {
    await page.goto('/#rules');
    await page.waitForTimeout(2000);
    const text = await page.locator('body').textContent();
    expect(text).toContain('Transaction');
    expect(text).toContain('regional_health_810');
  });

  test('Config page shows regional_health_810 config', async ({ page }) => {
    await page.goto('/#config');
    await page.waitForTimeout(2000);
    const text = await page.locator('body').textContent();
    expect(text).toContain('regional_health_810');
    expect(text).toContain('RegionalHealth');
  });
});

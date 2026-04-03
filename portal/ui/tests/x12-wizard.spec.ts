import { test, expect } from '@playwright/test';
import { execSync } from 'child_process';
import { writeFileSync, unlinkSync } from 'fs';
import { resolve, join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const API_BASE = 'http://localhost:18041';
const TEST_PROFILE = '_pw_x12_test';
const PROJECT_ROOT = resolve(__dirname, '..', '..', '..');

function cleanupProfile(profileName: string): void {
  const scriptPath = join(PROJECT_ROOT, '_pw_cleanup.py');
  const script = [
    'import yaml',
    'from pathlib import Path',
    `cfg = Path(r"${join(PROJECT_ROOT, 'config', 'config.yaml')}")`,
    'data = yaml.safe_load(cfg.read_text())',
    `data.get("compare",{}).get("profiles",{}).pop("${profileName}", None)`,
    `data.get("csv_schema_registry",{}).pop("${profileName}", None)`,
    'cfg.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))',
    `Path(r"${join(PROJECT_ROOT, 'config', 'compare_rules', profileName + '.yaml')}").unlink(missing_ok=True)`,
  ].join('\n');
  try {
    writeFileSync(scriptPath, script);
    execSync(`python "${scriptPath}"`, { cwd: PROJECT_ROOT });
  } catch {
    // best-effort cleanup
  } finally {
    try { unlinkSync(scriptPath); } catch { /* ignore */ }
  }
}

test.describe('X12 Wizard E2E', () => {
  test.afterEach(async () => {
    cleanupProfile(TEST_PROFILE);
  });

  test('Onboard page shows X12 EDI and Flat-File format options', async ({ page }) => {
    await page.goto('/#onboard');
    await page.waitForTimeout(2000);

    const x12Btn = page.getByText('X12 EDI');
    const flatBtn = page.getByText('Flat-File / XML');

    await expect(x12Btn).toBeVisible();
    await expect(flatBtn).toBeVisible();

    // Both should be clickable buttons
    const x12El = page.locator('button', { hasText: 'X12 EDI' });
    const flatEl = page.locator('button', { hasText: 'Flat-File / XML' });
    await expect(x12El).toBeEnabled();
    await expect(flatEl).toBeEnabled();
  });

  test('Selecting X12 EDI loads transaction type dropdown', async ({ page }) => {
    await page.goto('/#onboard');
    await page.waitForTimeout(2000);

    await page.locator('button', { hasText: 'X12 EDI' }).click();
    await page.waitForTimeout(2000);

    // Transaction type select should appear
    const select = page.locator('select');
    await expect(select).toBeVisible();

    // Should have an option containing "810"
    const option810 = select.locator('option', { hasText: '810' });
    await expect(option810).toBeAttached();

    // Card header should show "Select X12 Transaction Type"
    await expect(page.getByText('Select X12 Transaction Type')).toBeVisible();
  });

  test('Selecting 810 and clicking Review Schema shows fields table', async ({ page }) => {
    await page.goto('/#onboard');
    await page.waitForTimeout(2000);

    await page.locator('button', { hasText: 'X12 EDI' }).click();
    await page.waitForTimeout(2000);

    // Select 810
    await page.locator('select').selectOption('810');

    // Click Review Schema
    await page.getByRole('button', { name: 'Review Schema' }).click();
    await page.waitForTimeout(2000);

    // Schema Review card should appear
    await expect(page.getByText('Schema Review')).toBeVisible();

    // Field count badge
    await expect(page.getByText('fields')).toBeVisible();

    // At least one field row references BEG segment (source column shows "BEG.02" etc.)
    await expect(page.getByText('BEG.02')).toBeVisible();

    // Match key default shows BIG.BIG02
    await expect(page.getByText('BIG.BIG02')).toBeVisible();
  });

  test('Mode toggle switches between Existing Type and Upload New Mapping', async ({ page }) => {
    await page.goto('/#onboard');
    await page.waitForTimeout(2000);

    await page.locator('button', { hasText: 'X12 EDI' }).click();
    await page.waitForTimeout(2000);

    // "Existing Type" should be active, select visible
    const existingBtn = page.getByRole('button', { name: 'Existing Type' });
    const uploadBtn = page.getByRole('button', { name: 'Upload New Mapping' });
    await expect(existingBtn).toBeVisible();
    await expect(page.locator('select')).toBeVisible();

    // Click "Upload New Mapping"
    await uploadBtn.click();
    await page.waitForTimeout(500);

    // File input should appear, select should be gone
    await expect(page.locator('input[type="file"]')).toBeVisible();
    await expect(page.locator('select')).not.toBeVisible();

    // Click "Existing Type" — select returns
    await existingBtn.click();
    await page.waitForTimeout(500);
    await expect(page.locator('select')).toBeVisible();
  });

  test('Next: Register Partner button appears after schema review', async ({ page }) => {
    await page.goto('/#onboard');
    await page.waitForTimeout(2000);

    await page.locator('button', { hasText: 'X12 EDI' }).click();
    await page.waitForTimeout(2000);

    await page.locator('select').selectOption('810');
    await page.getByRole('button', { name: 'Review Schema' }).click();
    await page.waitForTimeout(2000);

    // "Next: Register Partner" should be visible and enabled
    const nextBtn = page.getByRole('button', { name: 'Next: Register Partner' });
    await expect(nextBtn).toBeVisible();
    await expect(nextBtn).toBeEnabled();

    // Click it to advance to Step 2
    await nextBtn.click();
    await page.waitForTimeout(2000);

    // Step 2: Register Partner heading visible
    await expect(page.getByText('Register Trading Partner')).toBeVisible();

    // Transaction type should be pre-filled with "810"
    const txnInput = page.locator('input').filter({ hasText: /810/ });
    // The transaction type is in an Input component — check the input value
    const txnField = page.locator('input[placeholder="810"]');
    await expect(txnField).toHaveValue('810');
  });

  test('Match key auto-populates with BIG / BIG02 for 810', async ({ page }) => {
    await page.goto('/#onboard');
    await page.waitForTimeout(2000);

    // Step 0: select X12 EDI
    await page.locator('button', { hasText: 'X12 EDI' }).click();
    await page.waitForTimeout(2000);

    // Step 1: select 810, review schema, advance
    await page.locator('select').selectOption('810');
    await page.getByRole('button', { name: 'Review Schema' }).click();
    await page.waitForTimeout(2000);
    await page.getByRole('button', { name: 'Next: Register Partner' }).click();
    await page.waitForTimeout(2000);

    // "X12 Segment/Field" toggle should be active (not "JSON Path")
    await expect(page.getByRole('button', { name: 'X12 Segment/Field' })).toBeVisible();

    // Segment input should have value "BIG"
    const segmentInput = page.locator('input[placeholder="BIG"]');
    await expect(segmentInput).toHaveValue('BIG');

    // Field input should have value "BIG02"
    const fieldInput = page.locator('input[placeholder="BIG02"]');
    await expect(fieldInput).toHaveValue('BIG02');
  });
});
